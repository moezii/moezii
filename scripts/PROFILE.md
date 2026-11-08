Edit `profile.json` to change the visible words and tools. The SVGs and README
are generated from that file.

```sh
python scripts/gen_assets.py
python scripts/gen_assets.py --refresh-streaks
```

The activity pane uses the same public provider as the previous README:
[GitHub Readme Streak Stats](https://github.com/DenverCoder1/github-readme-streak-stats).
Its documented JSON response supplies contribution totals and streak lengths/dates.
`assets/streak.json` stores the validated aggregate snapshot and its retrieval time.
No personal token, repository names, or commit contents are fetched.

The workflow runs daily at 04:23 UTC and can also be started manually. It becomes
active after these files are committed to the profile repository's default branch
with GitHub Actions enabled. Its automatic token only writes to this repository.
If fetching or validating a response fails, the workflow leaves the existing
snapshot and rendered images unchanged.

Counts reflect what the provider can see on the public GitHub profile. To include
anonymized private activity, enable private contributions in GitHub's profile
contribution settings. The retrieval date is visible in the activity pane.

Desktop and mobile each have animated and reduced-motion versions. There is no
JavaScript, external font, nested remote image, or credential in the SVGs.
