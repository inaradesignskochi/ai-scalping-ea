-- Initialize TimescaleDB for AI Scalping EA
-- This script sets up the database schema for trading data storage

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create hypertables for time-series data
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(10,5),
    volume BIGINT,
    bid DECIMAL(10,5),
    ask DECIMAL(10,5),
    spread DECIMAL(10,5),
    data_type VARCHAR(50) -- 'tick', 'candle_1m', 'candle_5m', etc.
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_data_type ON market_data (data_type);

-- Model registry table
CREATE TABLE IF NOT EXISTS model_registry (
    agent_name VARCHAR(50) PRIMARY KEY,
    model_path TEXT NOT NULL,
    version VARCHAR(20) NOT NULL,
    performance_score DECIMAL(5,4) NOT NULL, -- 0.0000 to 1.0000
    status VARCHAR(20) NOT NULL DEFAULT 'inactive', -- 'active', 'inactive', 'deprecated'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB -- Store additional model info
);

-- Trade history table
CREATE TABLE IF NOT EXISTS trade_history (
    trade_id VARCHAR(50) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL, -- 'BUY', 'SELL'
    entry_price DECIMAL(10,5) NOT NULL,
    exit_price DECIMAL(10,5),
    lot_size DECIMAL(5,2) NOT NULL,
    pnl DECIMAL(10,2),
    commission DECIMAL(10,2) DEFAULT 0,
    swap DECIMAL(10,2) DEFAULT 0,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    duration_minutes INTEGER,
    confidence DECIMAL(5,4),
    reason TEXT,
    agent_signals JSONB, -- Store signals from each agent
    ticket_number BIGINT,
    magic_number INTEGER,
    status VARCHAR(20) DEFAULT 'open', -- 'open', 'closed', 'cancelled'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('trade_history', 'entry_time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trade_history (symbol);
CREATE INDEX IF NOT EXISTS idx_trade_history_status ON trade_history (status);
CREATE INDEX IF NOT EXISTS idx_trade_history_entry_time ON trade_history (entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_trade_history_pnl ON trade_history (pnl);

-- AI performance metrics table
CREATE TABLE IF NOT EXISTS ai_performance (
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_name VARCHAR(50) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value DECIMAL(10,4),
    metadata JSONB
);

-- Convert to hypertable
SELECT create_hypertable('ai_performance', 'timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_ai_performance_agent ON ai_performance (agent_name);
CREATE INDEX IF NOT EXISTS idx_ai_performance_metric ON ai_performance (metric_name);

-- System health monitoring
CREATE TABLE IF NOT EXISTS system_health (
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    component VARCHAR(50) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value DECIMAL(10,4),
    status VARCHAR(20), -- 'healthy', 'warning', 'critical'
    message TEXT
);

-- Convert to hypertable
SELECT create_hypertable('system_health', 'timestamp', if_not_exists => TRUE);

-- News and sentiment data
CREATE TABLE IF NOT EXISTS news_sentiment (
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    headline TEXT,
    content TEXT,
    sentiment DECIMAL(3,2), -- -1.00 to 1.00
    relevance_score DECIMAL(3,2), -- 0.00 to 1.00
    url TEXT,
    metadata JSONB
);

-- Convert to hypertable
SELECT create_hypertable('news_sentiment', 'timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_news_sentiment_symbol ON news_sentiment (symbol);
CREATE INDEX IF NOT EXISTS idx_news_sentiment_sentiment ON news_sentiment (sentiment);
CREATE INDEX IF NOT EXISTS idx_news_sentiment_source ON news_sentiment (source);

-- Backtesting results
CREATE TABLE IF NOT EXISTS backtest_results (
    backtest_id VARCHAR(50) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_balance DECIMAL(10,2) NOT NULL,
    final_balance DECIMAL(10,2),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5,4),
    total_pnl DECIMAL(10,2),
    max_drawdown DECIMAL(10,2),
    sharpe_ratio DECIMAL(5,4),
    sortino_ratio DECIMAL(5,4),
    calmar_ratio DECIMAL(5,4),
    expectancy DECIMAL(10,4),
    avg_win DECIMAL(10,2),
    avg_loss DECIMAL(10,2),
    profit_factor DECIMAL(5,4),
    recovery_factor DECIMAL(5,4),
    parameters JSONB, -- Strategy parameters used
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_backtest_results_symbol ON backtest_results (symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_results_win_rate ON backtest_results (win_rate);

-- Insert default model registry entries
INSERT INTO model_registry (agent_name, model_path, version, performance_score, status, metadata) VALUES
('technical', '/app/models/technical_lstm_v1.pkl', '1.0.0', 0.5500, 'active', '{"architecture": "LSTM", "input_features": ["OHLCV", "RSI", "MACD"], "lookback": 60}'),
('sentiment', '/app/models/sentiment_bert_v1.pkl', '1.0.0', 0.5200, 'active', '{"architecture": "BERT", "preprocessing": "tokenization"}'),
('price_prediction', '/app/models/price_cnn_lstm_v1.pkl', '1.0.0', 0.5300, 'active', '{"architecture": "CNN-LSTM", "prediction_horizon": 5}'),
('risk_assessment', '/app/models/risk_xgboost_v1.pkl', '1.0.0', 0.5800, 'active', '{"architecture": "XGBoost", "features": ["ATR", "spread", "volatility"]}')
ON CONFLICT (agent_name) DO NOTHING;

-- Create continuous aggregates for performance monitoring
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_trade_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', entry_time) AS day,
    symbol,
    COUNT(*) AS total_trades,
    COUNT(*) FILTER (WHERE pnl > 0) AS winning_trades,
    COUNT(*) FILTER (WHERE pnl < 0) AS losing_trades,
    ROUND(AVG(pnl), 2) AS avg_pnl,
    ROUND(SUM(pnl), 2) AS total_pnl,
    ROUND(AVG(confidence), 4) AS avg_confidence
FROM trade_history
WHERE status = 'closed'
GROUP BY day, symbol
WITH NO DATA;

-- Add refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('daily_trade_summary',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Create retention policies (keep data for 1 year)
SELECT add_retention_policy('market_data', INTERVAL '1 year');
SELECT add_retention_policy('ai_performance', INTERVAL '1 year');
SELECT add_retention_policy('system_health', INTERVAL '6 months');
SELECT add_retention_policy('news_sentiment', INTERVAL '3 months');

-- Create function to update model performance
CREATE OR REPLACE FUNCTION update_model_performance()
RETURNS TRIGGER AS $$
BEGIN
    -- Update performance score based on recent trades
    IF NEW.status = 'closed' THEN
        UPDATE model_registry
        SET performance_score = (
            SELECT COALESCE(AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END), 0.5)
            FROM trade_history
            WHERE agent_name = NEW.agent_name
            AND entry_time > NOW() - INTERVAL '24 hours'
        ),
        updated_at = NOW()
        WHERE agent_name = NEW.agent_name;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for automatic performance updates
CREATE TRIGGER update_model_performance_trigger
    AFTER INSERT OR UPDATE ON trade_history
    FOR EACH ROW
    EXECUTE FUNCTION update_model_performance();

-- Grant permissions (adjust as needed for your setup)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trader;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trader;