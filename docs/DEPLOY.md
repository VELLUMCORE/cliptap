# Deploying the ClipTap website with GitHub Pages

The website is stored in this repository under `docs/`.

## GitHub Pages

1. Push this repository to GitHub.
2. Open the repository settings.
3. Go to **Pages**.
4. Set **Source** to **Deploy from a branch**.
5. Select the `main` branch.
6. Select the `/docs` folder.
7. Save.

GitHub will publish the site at the default GitHub Pages domain.

## Screenshot images

Add real screenshots to:

```text
docs/assets/screenshots/
```

The landing page already references the expected filenames. Missing screenshots are replaced with simple fallback blocks until real images are added.
