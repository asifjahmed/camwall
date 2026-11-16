"""Learning from the user's marks. In the wall's list of alerts, an alert can be marked Real or Wrong (the server
keeps those in marks.json); that teaches the detector what these vehicles look like on the user's cameras:

  - a vehicle very like one marked Wrong (the same look-alike parked by the road, say) doesn't alert again;
  - once a kind has MIN_REAL alerts marked Real, a small classifier for it (logistic regression on both models'
    embeddings) is trained against the Wrong ones and a sample of the ordinary vehicles the detector has seen
    (ordinary.pt, collected as it watches). It then has to agree with a hit by description, and can make one itself
    when very sure (models.LEARNED, AGREE).

Each snapshot carries its vehicle's embeddings (the crop, mirrored, and in greyscale), so a mark needs no work beyond
training. Training is in the background, within a minute of the marks changing.
"""

import base64
import random
import threading
import time

import torch

from app import paths

from .models import LABELS

MARKS = paths.USER / "marks.json"          # snapshot (path under detections/) -> "real" | "wrong"
ORDINARY = paths.USER / "models" / "ordinary.pt"
DETECTIONS = paths.USER / "detections"
ORDINARY_MAX = 20000     # ordinary vehicles kept as counter-examples
ORDINARY_SAMPLE = 0.2    # share of the ordinary vehicles judged that are kept (a car waiting at a light isn't kept 50 times)
ORDINARY_SAVE = 600      # s between saves of them
MIN_ORDINARY = 300       # ordinary vehicles needed before a classifier is trained
MIN_REAL = 3             # Real marks of a kind before it gets a classifier
LIKE_WRONG = 0.93        # likeness (cosine) to a vehicle marked Wrong at which a hit doesn't alert
CHECK_EVERY = 30         # s between looks at the marks
WEIGHT_DECAY = 0.03
STEPS = 400


def pack(embeddings):
    """Embeddings for a snapshot's .json: {"shape", "data" (base64 of float16)}."""
    x = embeddings.detach().to("cpu", torch.float16).contiguous()
    return {"shape": list(x.shape), "data": base64.b64encode(x.numpy().tobytes()).decode()}


def unpack(packed):
    data = bytearray(base64.b64decode(packed["data"]))
    return torch.frombuffer(data, dtype=torch.float16).reshape(packed["shape"]).float()


def train(positives, negatives):
    torch.manual_seed(0)
    x = torch.cat([positives, negatives])
    y = torch.cat([torch.ones(len(positives)), torch.zeros(len(negatives))])
    mean, spread = x.mean(0), x.std(0) + 1e-6
    x = (x - mean) / spread
    linear = torch.nn.Linear(x.shape[1], 1)
    optimiser = torch.optim.Adam(linear.parameters(), lr=1e-2, weight_decay=WEIGHT_DECAY)
    weight = torch.tensor(len(negatives) / len(positives))  # (the few marks count as much as all the rest)
    for _ in range(STEPS):
        optimiser.zero_grad()
        torch.nn.functional.binary_cross_entropy_with_logits(linear(x).squeeze(1), y, pos_weight=weight).backward()
        optimiser.step()
    return mean, spread, linear


class Learner:
    def __init__(self, log):
        self.log = log
        self.models = {}         # kind -> (mean, spread, linear)
        self.wrong = {}          # kind -> embeddings of vehicles marked Wrong as that kind
        self.marks_seen = None
        self.checked = 0.0
        self.training = None
        try:
            self.ordinary = torch.load(ORDINARY, weights_only=True).float() if ORDINARY.exists() else torch.empty(0)
        except (OSError, RuntimeError):
            self.ordinary = torch.empty(0)
        self.seen_ordinary = len(self.ordinary)
        self.saved = time.monotonic()
        self.lock = threading.Lock()

    # ---- as it watches ----

    def add_ordinary(self, embedding):
        """An ordinary vehicle (no kind came close): kept now and then, as a counter-example."""
        if random.random() > ORDINARY_SAMPLE:
            return
        with self.lock:
            self.seen_ordinary += 1
            row = embedding.detach().float().cpu().unsqueeze(0)
            if len(self.ordinary) < ORDINARY_MAX:
                self.ordinary = torch.cat([self.ordinary.reshape(-1, row.shape[1]), row])
            elif (i := random.randrange(self.seen_ordinary)) < ORDINARY_MAX:  # (an even sample of all seen)
                self.ordinary[i] = row[0]
        if time.monotonic() - self.saved > ORDINARY_SAVE:
            self.save()

    def save(self):
        self.saved = time.monotonic()
        with self.lock:
            ordinary = self.ordinary.to(torch.float16).clone()
        ORDINARY.parent.mkdir(parents=True, exist_ok=True)
        tmp = ORDINARY.with_suffix(".tmp")
        torch.save(ordinary, tmp)
        tmp.replace(ORDINARY)

    def score(self, embeddings):
        """Per vehicle, {"<kind> learned": probability} for each kind with a classifier."""
        models = self.models
        if not models:
            return [{} for _ in range(len(embeddings))]
        x = embeddings.detach().float().cpu()
        with torch.no_grad():
            probs = {kind: torch.sigmoid(linear((x - mean) / spread).squeeze(1)).tolist()
                     for kind, (mean, spread, linear) in models.items()}
        return [{f"{kind} learned": p[i] for kind, p in probs.items()} for i in range(len(x))]

    def like_wrong(self, kind, embedding):
        """Whether a vehicle is very like one marked Wrong as this kind."""
        wrong = self.wrong.get(kind)
        if wrong is None or not len(wrong):
            return False
        x = embedding.detach().float().cpu()
        return bool((torch.nn.functional.cosine_similarity(wrong, x.unsqueeze(0)) >= LIKE_WRONG).any())

    # ---- learning from the marks ----

    def refresh(self):
        """Within CHECK_EVERY s of the marks changing, train again (in the background)."""
        if time.monotonic() - self.checked < CHECK_EVERY or self.training and self.training.is_alive():
            return
        self.checked = time.monotonic()
        try:
            stamp = MARKS.stat().st_mtime
        except OSError:
            return
        if stamp == self.marks_seen:
            return
        self.marks_seen = stamp
        marks = paths.read_json(MARKS, {}) or {}
        self.training = threading.Thread(target=self._train, args=(marks,), daemon=True)
        self.training.start()

    def _train(self, marks):
        real, wrong = {k: [] for k in LABELS}, {k: [] for k in LABELS}
        for rel, verdict in marks.items():
            meta = paths.read_json(DETECTIONS / rel.replace(".jpg", ".json"))
            if not isinstance(meta, dict) or meta.get("kind") not in LABELS or "embeddings" not in meta:
                continue
            try:
                x = unpack(meta["embeddings"])
            except (ValueError, KeyError, RuntimeError, TypeError):
                continue
            (real if verdict == "real" else wrong)[meta["kind"]].append(x)
        self.wrong = {k: torch.cat([v[:1] for v in rows]) for k, rows in wrong.items() if rows}  # (as seen, not mirrored)
        with self.lock:
            ordinary = self.ordinary.clone()
        models = {}
        for kind in LABELS:
            if len(real[kind]) < MIN_REAL or len(ordinary) < MIN_ORDINARY:
                continue
            negatives = [ordinary, *wrong[kind], *(x[:1] for other in LABELS if other != kind for x in real[other])]
            models[kind] = train(torch.cat(real[kind]), torch.cat([n.reshape(-1, ordinary.shape[1]) for n in negatives]))
        self.models = models
        self.log("learned from your marks: " + ", ".join(f"{kind} {len(real[kind])} real, {len(wrong[kind])} wrong" for kind in LABELS)
                 + f"; classifiers for {', '.join(models) or 'none yet'} ({len(ordinary)} ordinary vehicles)")
