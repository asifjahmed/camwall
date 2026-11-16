# Security

Please report a vulnerability privately, through this repository's **Security › Report a vulnerability** page on
GitHub, not in a public issue. Say what's affected and how to reproduce it.

What camwall is meant to guarantee:

- Its pages and API answer only on this computer (127.0.0.1), and refuse requests made through another host name
  (DNS rebinding) or sent by another site's page.
- Phones and tablets get in only after pairing with a code shown on the computer, and only while that's turned on.
  A paired device can't change keys, add or change your own cameras (or see their passwords and recordings), let
  other devices in, or quit camwall.
- The relay fetches only the camera URLs the lists name, and only from public addresses, redirects included.
- Camera passwords are kept in the system keychain, or without one in a file only the user can read. They're never
  sent to a page.

A way around any of these is a vulnerability. One known limitation: while one of your own cameras is shown or
recorded, its password is on ffmpeg's command line, which other users of the same computer can see.
