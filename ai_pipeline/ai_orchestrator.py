import os
import psycopg2
import pickle
import numpy as np
from typing import Dict, List

class AIOrchestrator:
    def __init__(self):
        self.db = psycopg2.connect(os.environ.get("DATABASE_URL"))
        self.model_registry = {}
        self.active_agents = {}
        self.performance_metrics = {}
        
    def load_active_models(self):
        """Load models marked as 'active' in database"""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT agent_name, model_path, version, performance_score
            FROM model_registry
            WHERE status = 'active'
            ORDER BY performance_score DESC
        """)
        
        for row in cursor.fetchall():
            agent_name, model_path, version, score = row
            self.active_agents[agent_name] = {
                'model': self.load_model_from_path(model_path),
                'version': version,
                'score': score
            }

    def load_model_from_path(self, model_path):
        # Placeholder for loading a model from a file
        return None
    
    async def get_ensemble_signal(self, symbol: str, market_data: Dict) -> Dict:
        """Get aggregated signal from all active agents"""
        signals = []
        
        # Run all agents in parallel
        tasks = [
            self.run_agent('technical', symbol, market_data),
            self.run_agent('sentiment', symbol, market_data),
            self.run_agent('price_prediction', symbol, market_data),
            self.run_agent('risk_assessment', symbol, market_data)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Weighted voting based on recent performance
        ensemble_signal = self.weighted_vote(results)
        
        # Check confidence threshold
        if ensemble_signal['confidence'] < 0.75:
            return {'action': 'HOLD', 'confidence': 0, 'reason': 'Low confidence'}
        
        # Additional filters
        if not self.pre_trade_validation(symbol, ensemble_signal):
            return {'action': 'HOLD', 'confidence': 0, 'reason': 'Failed validation'}
        
        return ensemble_signal

    def pre_trade_validation(self, symbol, ensemble_signal):
        # Placeholder for pre-trade validation
        return True

    async def run_agent(self, agent_name, symbol, market_data):
        # Placeholder for running an agent
        return {'agent': agent_name, 'action': 'HOLD', 'confidence': 0, 'reason': 'Not implemented'}
    
    def weighted_vote(self, agent_results: List[Dict]) -> Dict:
        """Aggregate signals using performance-weighted voting""""
        votes = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        confidences = []
        reasons = []
        
        for result in agent_results:
            agent_name = result['agent']
            weight = self.active_agents[agent_name]['score']
            
            votes[result['action']] += weight * result['confidence']
            confidences.append(result['confidence'])
            reasons.append(f"{agent_name}: {result['reason']}")
        
        winning_action = max(votes, key=votes.get)
        final_confidence = np.mean(confidences)
        
        return {
            'action': winning_action,
            'confidence': final_confidence,
            'reason': ' | '.join(reasons),
            'votes': votes
        }
    
    def auto_switch_models(self):
        """Background task: Switch underperforming models"""
        cursor = self.db.cursor()
        
        # Calculate performance over last 100 trades
        cursor.execute("""
            SELECT agent_name, 
                   AVG(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as win_rate,
                   AVG(pnl) as avg_pnl
            FROM trade_history
            WHERE timestamp > NOW() - INTERVAL '24 hours'
            GROUP BY agent_name
        """)
        
        for agent_name, win_rate, avg_pnl in cursor.fetchall():
            # If performance drops below threshold, switch to backup model
            if win_rate < 0.45 or avg_pnl < -10:
                self.switch_to_backup_model(agent_name)

    def switch_to_backup_model(self, agent_name):
        # Placeholder for switching to a backup model
        pass