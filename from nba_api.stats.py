from nba_api.stats.endpoints import leaguegamelog as log, boxscoretraditionalv2 as trd, boxscoreadvancedv2 as adv, boxscorefourfactorsv2 as ffs, boxscoremiscv2 as msc, boxscoreplayertrackv2 as trk, boxscorescoringv2 as scr, boxscoreusagev2 as usg
import pandas as pd
import time

# Fetch all game IDs since 2015
seasons = ['2015-16', '2016-17', '2017-18', '2018-19', '2019-20', '2020-21', '2021-22', '2022-23', '2023-24', '2024-25']
game_ids = []

for season in seasons:
    gamelog = log.LeagueGameLog(season=season)
    games = gamelog.get_data_frames()[1]
    game_ids.extend(games['GAME_ID'].unique())
    time.sleep(1)  # Rate limit handling

# Fetch boxscore data for each game
def fetch_game_data(game_id):
    endpoints = {
        'trd': trd.BoxScoreTraditionalV2,
        'adv': adv.BoxScoreAdvancedV2,
        'ffs': ffs.BoxScoreFourFactorsV2,
        'msc': msc.BoxScoreMiscV2,
        'trk': trk.BoxScorePlayerTrackV2,

    }
    game_data = {}
    for key, endpoint in endpoints.items():
        bs = endpoint(game_id=game_id)
        team_stats = bs.get_data_frames()[1]  # Assuming team stats are in the second DataFrame
        game_data[key] = team_stats
        time.sleep(0.5)
    return game_data

# Combine all data into a single DataFrame
all_data = []
for gid in game_ids:
    data = fetch_game_data(gid)
    merged = pd.concat([df.set_index('TEAM_ID') for df in data.values()], axis=1).reset_index()
    merged['GAME_ID'] = gid
    all_data.append(merged)
    time.sleep(1)

final_df = pd.concat(all_data, ignore_index=True)