Set up `leagueid` number (see https://www.hltv.org/fantasy) and account details in `settings.yml`.
Then:

```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

To cache data for `leagueid`, start up:
```
python cache_boosters.py
```
Need to have a placeholder entry in the league already to cache all players.

To parse the resulting `.yml` dumps in `scraped/` into a dataframe (stored as `.pkl`) and excel sheet:
```
python parse_boosters.py
```