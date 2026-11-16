"""What the detector sees with: YOLO finds the vehicles in a frame, and two CLIP models judge each one against
descriptions of police cars, ambulances and fire trucks (and, if the user has added any, photos of their local police
liveries). The thresholds were worked out on ~9,000 ordinary vehicles and every emergency vehicle seen on Ohio road
cameras; a kind needs both models to agree, which kept out white vans, box trucks and dark SUVs that either model
alone took for one.

After dark, vehicles are judged in greyscale: headlight glare looks like police lights in colour.
"""

from math import asin, atan2, cos, degrees, radians, sin

import open_clip
import torch
from PIL import Image, ImageOps
from ultralytics import YOLO

YOLO_SIZE = 1280              # camera frames hold many small vehicles
VEHICLE_CLASSES = {2, 5, 7}   # COCO car, bus, truck
MIN_WIDTH = 56                # px; smaller vehicles are too few pixels to judge
POLICE_MODEL = ("ViT-B-32", "laion2b_s34b_b79k")  # best at telling police liveries from look-alikes
TYPE_MODEL = ("ViT-B-16-SigLIP", "webli")         # fewest ordinary vehicles taken for ambulances or fire trucks
DESCRIPTIONS = {
    "police": ["a police car", "a police SUV", "a black sheriff SUV with gold stripes and a star on the door",
               "a police SUV with white doors and POLICE written on the side", "a police car with a light bar on the roof"],
    "ambulance": ["an ambulance", "a white and red ambulance truck"],
    "fire": ["a fire truck", "a red fire engine"],
    "other": ["a car", "a sedan", "an SUV", "a black SUV", "a dark gray SUV", "a pickup truck", "a minivan",
              "a white van", "a delivery truck", "a box truck", "a school bus", "a semi truck", "a city bus",
              "a garbage truck", "a construction vehicle", "a taxi", "a motorcycle", "a trailer", "a semi truck at night"],
}
LABELS = {"police": "Police", "ambulance": "Ambulance", "fire": "Fire truck"}
THRESHOLD = {"police photo": 0.70, "police": 0.7, "ambulance": 0.7, "fire": 0.85}
SECOND_OPINION = {"police": 0.8, "ambulance": 0.5, "fire": 0.5}
SMALL = (110, 0.75)           # police by description alone needs 0.75 on vehicles under 110 px wide
NEAR = {"police photo": 0.62, "police": 0.6, "ambulance": 0.5, "fire": 0.5}  # near misses, kept for review
# Once the user's marks have trained a kind's classifier (learn.py): it must agree with a hit by description (AGREE),
# and alone makes a hit when at least LEARNED[kind][0] with that kind's descriptions at least LEARNED[kind][1]. (As on
# the Ohio cameras they were tuned on, where these cut the false police alerts from glinting dark SUVs and white work trucks.)
AGREE = {"police": 0.7, "ambulance": 0.5, "fire": 0.5}
LEARNED = {"police": (0.9, 0.5), "ambulance": (0.9, 0.3), "fire": (0.9, 0.3)}
DARK_BELOW = 3                # sun elevation in degrees under which crops are judged in greyscale


class Clip:
    def __init__(self, spec, device):
        self.device = device
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(spec[0], pretrained=spec[1], device=device)
        self.model.eval()
        self.tokenizer = open_clip.get_tokenizer(spec[0])

    @torch.no_grad()
    def images(self, crops):
        x = self.model.encode_image(torch.stack([self.preprocess(c) for c in crops]).to(self.device))
        return x / x.norm(dim=-1, keepdim=True)

    @torch.no_grad()
    def texts(self, texts):
        x = self.model.encode_text(self.tokenizer(texts).to(self.device))
        return x / x.norm(dim=-1, keepdim=True)


def best_device():
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class Detector:
    def __init__(self, yolo_weights, references, log):
        """yolo_weights: where yolo11s.pt is (or goes: it's downloaded the first time). references: photos of local
        police or sheriff vehicles (may be none)."""
        self.device = best_device()
        self.yolo = YOLO(str(yolo_weights))
        self.typer = Clip(TYPE_MODEL, self.device)
        self.groups = [g for g, items in DESCRIPTIONS.items() for _ in items]
        prompts = [f"a traffic camera photo of {t}" for items in DESCRIPTIONS.values() for t in items]
        self.text = self.typer.texts(prompts)
        self.matcher = Clip(POLICE_MODEL, self.device)
        self.matcher_text = self.matcher.texts(prompts)
        crops = []
        for path in references:
            try:
                img = Image.open(path).convert("RGB")
            except OSError:
                continue
            boxes = self.vehicles(img, 640)  # close-ups: the camera-frame size misses big vehicles
            if boxes:
                vehicle = crop(img, max(boxes, key=area))
                crops += [vehicle, ImageOps.mirror(vehicle)]  # (the livery seen driving the other way)
            else:
                log(f"{path.name}: no vehicle found in it, so it's not used")
        self.refs = self.matcher.images(crops) if crops else None
        log(f"models ready on {self.device}; {len(crops) // 2} photos of local police vehicles")

    def vehicles(self, img, size=YOLO_SIZE):
        r = self.yolo.predict(img, imgsz=size, device=self.device, conf=0.3, verbose=False)[0]
        return [tuple(b) for c, b in zip(r.boxes.cls.tolist(), r.boxes.xyxy.tolist()) if int(c) in VEHICLE_CLASSES]

    def judge(self, crops):
        """Per crop: likeness to a local police photo, and both models' police / ambulance / fire probabilities; and
        both models' embeddings of the crops, side by side (what learn.py learns from)."""
        matched = self.matcher.images(crops)
        typed_images = self.typer.images(crops)
        likeness = (matched @ self.refs.T).max(dim=1).values.cpu().tolist() if self.refs is not None else [0.0] * len(crops)
        typed = self.probs(typed_images @ self.text.T)
        checked = self.probs(matched @ self.matcher_text.T)
        scores = [{"police photo": ref, **t, **{f"{k} check": v for k, v in c.items()}} for ref, t, c in zip(likeness, typed, checked)]
        return scores, torch.cat([typed_images, matched], dim=1).cpu()

    def embed(self, crops):
        """Both models' embeddings of crops, side by side."""
        return torch.cat([self.typer.images(crops), self.matcher.images(crops)], dim=1).cpu()

    def probs(self, similarity):
        rows = (100 * similarity).softmax(dim=-1).cpu()
        return [{k: sum(p for p, g in zip(row.tolist(), self.groups) if g == k) for k in LABELS} for row in rows]


def verdict(scores, width):
    """The kind of emergency vehicle these scores say a vehicle `width` px wide is, or None."""
    if scores["police photo"] >= THRESHOLD["police photo"]:
        return "police"
    for kind in LABELS:
        needed = max(THRESHOLD[kind], SMALL[1]) if kind == "police" and width < SMALL[0] else THRESHOLD[kind]
        agrees = scores.get(kind + " learned", 1.0) >= AGREE[kind]  # (no classifier yet: no say)
        if scores[kind] >= needed and scores[kind + " check"] >= SECOND_OPINION[kind] and agrees:
            return kind
        if scores.get(kind + " learned", 0) >= LEARNED[kind][0] and scores[kind] >= LEARNED[kind][1]:
            return kind
    return None


def ordinary(scores):
    """Whether no kind came anywhere near: a vehicle to learn as an ordinary one."""
    return scores["police photo"] < 0.5 and all(scores[k] < 0.2 and scores.get(k + " learned", 0) < 0.2 for k in LABELS)


def near_miss(scores, kinds):
    return any(scores.get(g, 0) >= NEAR[g] for g in NEAR if g.split()[0] in kinds)


def tag(scores):
    """e.g. "photo 0.64 police 0.90+0.99 ambulance 0.01+0.00 fire 0.00+0.00" (description + second opinion), and the
    learned classifiers' if there are any."""
    learned = [f"{k} {scores[k + ' learned']:.2f}" for k in LABELS if k + " learned" in scores]
    return f"photo {scores['police photo']:.2f} " + " ".join(
        f"{kind} {scores[kind]:.2f}+{scores[kind + ' check']:.2f}" for kind in LABELS) + (f" learned {' '.join(learned)}" if learned else "")


def sun_elevation(t, lat, lon):
    """Degrees of the sun above the horizon at unix time t, at lat, lon (well under a degree off)."""
    d = t / 86400 - 10957.5  # days since 2000-01-01 12:00 UTC
    g = radians(357.529 + 0.98560028 * d)
    ecliptic = radians(280.459 + 0.98564736 * d + 1.915 * sin(g) + 0.020 * sin(2 * g))
    tilt = radians(23.439 - 0.00000036 * d)
    ra, dec = atan2(cos(tilt) * sin(ecliptic), cos(ecliptic)), asin(sin(tilt) * sin(ecliptic))
    hour_angle = radians((280.46061837 + 360.98564736629 * d + lon) % 360) - ra
    return degrees(asin(sin(radians(lat)) * sin(dec) + cos(radians(lat)) * cos(dec) * cos(hour_angle)))


def dark(t, lat, lon):
    return lat is not None and lon is not None and sun_elevation(t, lat, lon) < DARK_BELOW


def crop(img, box, pad=0.08):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    return img.crop((max(0, x1 - pad * w), max(0, y1 - pad * h), min(img.width, x2 + pad * w), min(img.height, y2 + pad * h)))


def area(b):
    return (b[2] - b[0]) * (b[3] - b[1])


def overlap(a, b):
    """Share of box a that box b covers."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy / area(a) if area(a) else 0.0


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / (area(a) + area(b) - inter) if inter else 0.0
