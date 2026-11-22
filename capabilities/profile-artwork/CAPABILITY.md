# Portable GitHub profile artwork

Use a single Python script to generate and version profile artwork for a new
GitHub account or an existing profile repository. The renderer makes three
matching animations and reduced-motion PNGs from two chosen colors. You can
also import your own set of artwork into the same release and rollback flow.

## Start a profile

Create or clone the public GitHub repository whose name matches your account
login. Download [profile_artwork.py](profile_artwork.py) beside that checkout.
The script runs locally with Python 3.10 or later and Pillow.

From the new profile checkout:

```sh
python -m pip install "Pillow>=11,<14"
python ../profile_artwork.py init --account your-login --title "Your Name" --tagline "What you make"
python ../profile_artwork.py build
python ../profile_artwork.py verify
```

Edit the README prose directly. Move a whole marked artwork block to position
it around your own sections. Keep the opening, continuation, and footer in
that order. To change the palette, edit the color values in
`profile-artwork.json` and run `build` again. Every build writes a new numbered
release and matching stills under `assets/profile-artwork/`. Commit the README,
config and release directory to your profile's default branch and push using
your ordinary Git credentials.

Once GitHub shows the updated profile, verify the public markup and hosted
bytes with `python ../profile_artwork.py verify --live`. The footer GIF links to
the configured account's public repositories. Account creation, repository
permissions, credentials, visual approval and pushing remain with the owner.

## Bring existing artwork forward

Run `python ../profile_artwork.py build --from-assets /path/to/media`
with one GIF and one same-size PNG for each basename:

- `stitch-descent`
- `stitch-resume`
- `stitch-pulse`

Imported files are preserved byte-for-byte. GIFs must be animated, sized for
a profile column, at most five seconds per cycle and at most 250 kB combined.
Keep source art you have permission to publish. The archived EndeavorEverlasting
V11 animations are a proven compatible input for the account owner's use.
The profile's separate SVG hero and editorial copy belong to that project.

## Inspect and roll back

`status` returns the selected version, local verification result and versions
available for restore. For example:

```sh
python ../profile_artwork.py status
python ../profile_artwork.py restore v01
python ../profile_artwork.py verify
```

Restore replaces the three marked artwork blocks and verifies the target
files against their manifest. README prose outside those blocks and previous
release files are preserved. Commit the README change to publish the rollback.

## Contract and proof

Automation owns `profile-artwork/v1`. The consumer provides the GitHub
login, title, tagline, optional color pair and optional media. The CLI emits
JSON and fails with a nonzero exit code on malformed input, media errors,
integrity failures or a conflicting edit. The local manifest stores SHA-256
digests for the six files. The GitHub read-only check verifies public layout,
reduced-motion sources, the invitation link and served bytes.

The isolated tests run a copied script against fresh consumer directories.
They cover first generation, new palettes, exact import, verified rollback
with edited copy, mobile-width decoded frames, and synthetic public readback.
A separate local Git canary imports V11's actual GIFs and PNGs. A consumer's
own publication is verified by running the public check after their push.

```sh
python -B -m unittest discover -s capabilities/profile-artwork/tests -v
```
