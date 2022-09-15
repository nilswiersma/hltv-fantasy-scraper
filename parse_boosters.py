import yaml
import pandas as pd

def parse_it(line):
    line = eval(line)
    line = line.split('\n')
    name = line[0]
    game = line[1]
    percentage = line[2].replace('%', '')
    return name, game, percentage

with open('settings.yml', 'r') as f:
    settings = yaml.safe_load(f)
    leagueid = settings['leagueid']

with open(f'.scraped-{leagueid}.yml', 'r') as inf:
    scraped = yaml.safe_load(inf)

data = []
for booster, players in scraped.items():
    print(booster)
    for playerstr in players:
        name, game, percentage = parse_it(playerstr)
        print(name, percentage)
        data.append({'booster': booster, 'name': name, 'percentage': percentage})

df = pd.DataFrame(data)
with pd.ExcelWriter(f'spreadsheets/{leagueid}.xlsx') as writer:
    df.pivot(index='name', columns='booster').to_excel(writer)
