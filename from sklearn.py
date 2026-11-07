from sklearn.ensemble import RandomForestClassifier
import mlflow
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

class WinProbabilityModel:
    def __init__(self):
        self.features = [
            'FG_PCT', 'FG3_PCT', 'FT_PCT', 'REB', 'AST', 
            'STL', 'BLK', 'TOV', 'PACE', 'PLUS_MINUS'
        ]
        self.model = RandomForestClassifier(n_estimators=100)
        
    def prepare_data(self, df: pd.DataFrame):
        # Create target variable (1 for win, 0 for loss)
        df['WIN'] = (df['PLUS_MINUS'] > 0).astype(int)
        
        # Prepare features
        X = df[self.features]
        y = df['WIN']
        
        return train_test_split(X, y, test_size=0.2, random_state=42)
    
    def train_and_evaluate(self, df: pd.DataFrame):
        with mlflow.start_run():
            # Log parameters
            mlflow.log_params({
                "features": self.features,
                "model": "RandomForestClassifier"
            })
            
            # Prepare data
            X_train, X_test, y_train, y_test = self.prepare_data(df)
            
            # Train model
            self.model.fit(X_train, y_train)
            
            # Get feature importance
            importance = pd.DataFrame({
                'feature': self.features,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            # Log metrics
            mlflow.log_metric("accuracy", self.model.score(X_test, y_test))
            
            # Log feature importance plot
            fig = importance.plot(x='feature', y='importance', 
                                kind='bar', figsize=(10,6))
            mlflow.log_figure(fig.figure, "feature_importance.png")
            
            return importance