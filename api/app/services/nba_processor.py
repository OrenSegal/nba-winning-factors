from nba_api.stats.endpoints import (
    leaguegamelog as log,
    boxscoretraditionalv2 as trd,
    boxscoreadvancedv2 as adv,
    boxscorefourfactorsv2 as ffs,
    boxscoremiscv2 as msc,
    boxscoreplayertrackv2 as trk
)
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging
import time
import mlflow
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class NBADataProcessor:
    def __init__(self, seasons: List[str], job_id: str):
        """
        Initialize the NBA data processor.
        
        Args:
            seasons: List of seasons to process (e.g., ['2021-22'])
            job_id: Unique identifier for the processing job
        """
        self.seasons = seasons
        self.job_id = job_id
        self.progress = 0.0
        self.status = "initialized"
        self._setup_endpoints()

    def _setup_endpoints(self):
        """Configure NBA API endpoints."""
        self.endpoints = {
            'traditional': trd.BoxScoreTraditionalV2,
            'advanced': adv.BoxScoreAdvancedV2,
            'four_factors': ffs.BoxScoreFourFactorsV2,
            'misc': msc.BoxScoreMiscV2,
            'tracking': trk.BoxScorePlayerTrackV2
        }

    def _update_progress(self, value: float):
        """Update processing progress."""
        self.progress = min(100.0, max(0.0, value))
        self._log_progress()

    def _log_progress(self):
        """Log current progress to MLflow."""
        mlflow.log_metric(f"progress_{self.job_id}", self.progress)

    def _handle_rate_limiting(self):
        """Handle API rate limiting."""
        time.sleep(1)  # Basic rate limiting

    @staticmethod
    def _calculate_pace_factor(pace: float) -> float:
        """Calculate pace adjustment factor."""
        return 100 / pace if pace > 0 else 1.0

    def fetch_game_ids(self, season: str) -> List[str]:
        """
        Fetch game IDs for a given season.
        
        Args:
            season: NBA season (e.g., '2021-22')
            
        Returns:
            List of game IDs
        """
        try:
            gamelog = log.LeagueGameLog(season=season)
            games_df = gamelog.get_data_frames()[0]
            self._handle_rate_limiting()
            return games_df['GAME_ID'].unique().tolist()
        except Exception as e:
            logger.error(f"Error fetching game IDs for season {season}: {str(e)}")
            raise

    def fetch_game_data(self, game_id: str) -> Dict[str, pd.DataFrame]:
        """
        Fetch all boxscore data for a single game.
        
        Args:
            game_id: NBA game ID
            
        Returns:
            Dictionary of DataFrames containing game data
        """
        game_data = {}
        for endpoint_name, endpoint_class in self.endpoints.items():
            try:
                boxscore = endpoint_class(game_id=game_id)
                team_stats = boxscore.get_data_frames()[1]  # Team stats DataFrame
                game_data[endpoint_name] = team_stats
                self._handle_rate_limiting()
            except Exception as e:
                logger.error(f"Error fetching {endpoint_name} data for game {game_id}: {str(e)}")
                raise
        return game_data

    def adjust_to_pace_100(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adjust statistics to per-100 possessions.
        
        Args:
            df: DataFrame containing game statistics
            
        Returns:
            DataFrame with pace-adjusted statistics
        """
        pace_cols = [
            'PTS', 'FGM', 'FGA', 'FG3M', 'FG3A', 'FTM', 'FTA',
            'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF'
        ]
        
        df_adjusted = df.copy()
        pace_factors = df['PACE'].apply(self._calculate_pace_factor)
        
        for col in pace_cols:
            if col in df.columns:
                df_adjusted[col] = df[col] * pace_factors
        
        return df_adjusted

    def calculate_matchup_differences(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate differences between teams in the same game.
        
        Args:
            df: DataFrame containing game statistics
            
        Returns:
            DataFrame with added difference columns
        """
        diff_cols = [
            'PTS', 'FGM', 'FGA', 'FG3M', 'FG3A', 'FTM', 'FTA',
            'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF'
        ]
        
        result_dfs = []
        for game_id in df['GAME_ID'].unique():
            game_df = df[df['GAME_ID'] == game_id].copy()
            if len(game_df) == 2:  # Ensure we have both teams
                for col in diff_cols:
                    if col in df.columns:
                        game_df[f'{col}_DIFF'] = game_df[col] - game_df[col].iloc[::-1].values
                result_dfs.append(game_df)
        
        return pd.concat(result_dfs, ignore_index=True)

    def process_data(self) -> pd.DataFrame:
        """
        Main processing function to fetch and transform all data.
        
        Returns:
            Processed DataFrame containing all game statistics
        """
        all_game_data = []
        total_seasons = len(self.seasons)
        
        for season_idx, season in enumerate(self.seasons):
            logger.info(f"Processing season: {season}")
            try:
                game_ids = self.fetch_game_ids(season)
                total_games = len(game_ids)
                
                for game_idx, game_id in enumerate(game_ids):
                    logger.info(f"Processing game: {game_id}")
                    try:
                        # Fetch and combine all boxscore data
                        game_data = self.fetch_game_data(game_id)
                        
                        # Merge all boxscore types
                        merged = pd.concat(
                            [df.set_index('TEAM_ID') for df in game_data.values()],
                            axis=1
                        ).reset_index()
                        
                        # Remove duplicate columns
                        merged = merged.loc[:, ~merged.columns.duplicated()]
                        merged['GAME_ID'] = game_id
                        merged['SEASON'] = season
                        
                        all_game_data.append(merged)
                        
                        # Update progress
                        progress = (
                            (season_idx * 100 / total_seasons) +
                            (game_idx * 100 / total_games / total_seasons)
                        )
                        self._update_progress(progress)
                        
                    except Exception as e:
                        logger.error(f"Error processing game {game_id}: {str(e)}")
                        continue
                    
            except Exception as e:
                logger.error(f"Error processing season {season}: {str(e)}")
                continue

        # Combine all data
        if not all_game_data:
            raise ValueError("No data was successfully processed")
        
        final_df = pd.concat(all_game_data, ignore_index=True)
        
        # Adjust to per-100 possessions
        final_df = self.adjust_to_pace_100(final_df)
        
        # Calculate matchup differences
        final_df = self.calculate_matchup_differences(final_df)
        
        # Select and reorder columns
        essential_cols = ['GAME_ID', 'TEAM_NAME', 'MATCHUP', 'GAME_DATE', 'SEASON']
        stat_cols = [col for col in final_df.columns if col not in essential_cols]
        final_df = final_df[essential_cols + stat_cols]
        
        # Save processed data
        self._save_processed_data(final_df)
        
        return final_df

    def _save_processed_data(self, df: pd.DataFrame):
        """Save processed data to disk and log to MLflow."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"processed_data_{self.job_id}_{timestamp}.csv"
        
        # Save locally
        output_dir = Path("data/processed")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename
        df.to_csv(output_path, index=False)
        
        # Log to MLflow
        mlflow.log_artifact(str(output_path))
        
        # Log final metrics
        metrics = {
            "total_games": len(df["GAME_ID"].unique()),
            "avg_pace": df["PACE"].mean(),
            "avg_points": df["PTS"].mean(),
            "processing_complete": 100.0
        }
        for metric_name, value in metrics.items():
            mlflow.log_metric(f"{metric_name}_{self.job_id}", value)