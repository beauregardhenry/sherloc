# Security policy

## Report a vulnerability privately

Use GitHub's private vulnerability reporting: open the repository's **Security** tab and choose **Report a vulnerability**. Do not open a public issue or pull request for a security problem, and do not attach client data or real device dumps.

Include what you did, what you expected and what happened, and the Sherloc version or commit.

## What counts

Sherloc runs on a consultant's computer and stores client evidence there. These are in scope:

- a way to read, change or keep client data that "Delete client data" should remove
- running a command or reading a file by sending a crafted request, serial, app id or phone output
- a web page that can drive a local Sherloc instance (cross-site requests, DNS rebinding)
- a dependency with a known vulnerability that the code reaches

Known and documented limits are not vulnerabilities: Sherloc does not encrypt data at rest (the README recommends full-disk encryption), and it has no login because it listens on `127.0.0.1` only.
