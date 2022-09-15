Set up league id number (see https://www.hltv.org/fantasy) and account details in `settings.yml`.
Then:

```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```
```
python cache_boosters.py
```
```
python parse_boosters.py
```