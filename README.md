# Lichess games: exploratory analysis + win prediction

Exploratory analysis of ~19k real Lichess games and a logistic-regression model
for P(White wins), evaluated against the raw Elo formula as a baseline.

## Headline findings

- White scores 0.52 overall. The first-move edge is real but small, and shows up
  as fewer losses / more draws rather than more raw wins: at equal ratings
  White's mean score is 0.520 but P(White wins) is 0.494.
- Rating difference dominates everything else. The empirical outcome curve
  tracks the Elo sigmoid but with shallower tails. The big favourites win less
  often than the formula predicts (+500 gap: ~0.87 observed vs 0.95 predicted).
- A one-feature logistic regression on rating difference beats the raw Elo
  formula on log-loss (0.615 vs 0.621) with *identical* AUC (0.7155), a clean
  demonstration that calibration and discrimination are different properties.
- Opening features carry no predictive signal once ratings are known. They
  appeared to help on a single train/test split; 5-fold CV showed the gain was
  split noise. That failed iteration is left in the notebook on purpose.
- Honest ceiling for pre-game features on this data: AUC ≈ 0.72, log-loss ≈ 0.62.

## Repo structure

```
notebooks/lichess_analysis.ipynb   the analysis, executed with all outputs
scripts/parse_full_dump.py         stream a full monthly dump (.pgn.zst) into CSV
requirements.txt
```

## Running it

```bash
pip install -r requirements.txt
jupyter notebook notebooks/lichess_analysis.ipynb
```

The notebook downloads its data (~7.7 MB CSV) on first run. No manual data
setup needed.

## Data

The ~20k-game dataset collected via the Lichess API (the well-known Kaggle
"Chess Game Dataset", mirrored by [TidyTuesday](https://github.com/rfordatascience/tidytuesday/tree/master/data/2024/2024-10-01)).
Caveats: it is a convenience sample of API-active users, skews ~1400–1800
rated, and is ~85% rapid time control — so per-opening estimates are thin and
time-control comparisons are impossible. Directional patterns reproduce in the
full dump; exact percentages will wobble.

To scale up, download a month from [database.lichess.org](https://database.lichess.org)
(~30 GB compressed, ~100M games) and extract a sample:

```bash
python scripts/parse_full_dump.py lichess_db_standard_rated_2026-06.pgn.zst games_big.csv \
    --limit 500000 --every 50
```

Constant memory use; headers-only parsing. See the script docstring for schema
differences vs the small dataset and why `--every` matters (the dump is
time-ordered, so the first N games are a biased slice).
