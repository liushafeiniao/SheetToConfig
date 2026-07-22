Donation QR images are deliberately excluded from the public source tree.

Official publishers inject verified private images during the release build with
`scripts/inject_donation_assets.py --require`, so the official packaged app can
still show them. Public checkouts keep this directory image-free; when an image
is absent, the About dialog displays its safe missing-resource placeholder.
