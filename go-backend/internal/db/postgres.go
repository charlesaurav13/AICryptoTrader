package db

import (
	"context"
	"time"
	"github.com/jackc/pgx/v5/pgxpool"
)

type PgPool = pgxpool.Pool

func NewPostgres(dsn string) (*pgxpool.Pool, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	return pgxpool.New(ctx, dsn)
}

func NewTimescale(dsn string) (*pgxpool.Pool, error) {
	return NewPostgres(dsn)
}

type Trade struct {
	ID          int64      `json:"id"`
	Symbol      string     `json:"symbol"`
	Side        string     `json:"side"`
	Leverage    int        `json:"leverage"`
	Qty         float64    `json:"qty"`
	EntryPrice  float64    `json:"entry_price"`
	ExitPrice   *float64   `json:"exit_price"`
	ExitReason  *string    `json:"exit_reason"`
	SL          float64    `json:"sl"`
	TP          float64    `json:"tp"`
	RealizedPnl *float64   `json:"realized_pnl"`
	Fees        float64    `json:"fees"`
	OpenedTs    time.Time  `json:"opened_ts"`
	ClosedTs    *time.Time `json:"closed_ts"`
}

type Stats struct {
	TotalTrades int64   `json:"total_trades"`
	Wins        int64   `json:"wins"`
	Losses      int64   `json:"losses"`
	TotalPnl    float64 `json:"total_pnl"`
	TotalFees   float64 `json:"total_fees"`
	OpenCount   int64   `json:"open_count"`
	WinRate     float64 `json:"win_rate"`
}

type Decision struct {
	CorrelationID string      `json:"correlation_id"`
	AgentName     string      `json:"agent_name"`
	Output        interface{} `json:"output"`
	Reasoning     *string     `json:"reasoning"`
	Confidence    *float64    `json:"confidence"`
	Ts            time.Time   `json:"ts"`
}

type MLSignal struct {
	Symbol        string    `json:"symbol"`
	Ts            time.Time `json:"ts"`
	RegimePred    string    `json:"regime_pred"`
	DirectionPred string    `json:"direction_pred"`
	ShortDir      string    `json:"short_direction"`
	Confidence    float64   `json:"confidence"`
	SizeAdj       string    `json:"size_adjustment"`
	ModelVersion  string    `json:"model_version"`
}

type PnlPoint struct {
	Ts            time.Time `json:"ts"`
	RealizedPnl   float64   `json:"realized_pnl"`
	CumulativePnl float64   `json:"cumulative_pnl"`
}

func GetStats(ctx context.Context, pool *pgxpool.Pool) (*Stats, error) {
	row := pool.QueryRow(ctx, `
		SELECT
			COUNT(*),
			COUNT(*) FILTER (WHERE realized_pnl > 0),
			COUNT(*) FILTER (WHERE realized_pnl <= 0 AND closed_ts IS NOT NULL),
			COALESCE(SUM(realized_pnl), 0),
			COALESCE(SUM(fees), 0),
			COUNT(*) FILTER (WHERE closed_ts IS NULL)
		FROM trades`)
	var s Stats
	if err := row.Scan(&s.TotalTrades, &s.Wins, &s.Losses, &s.TotalPnl, &s.TotalFees, &s.OpenCount); err != nil {
		return nil, err
	}
	if closed := s.Wins + s.Losses; closed > 0 {
		s.WinRate = float64(s.Wins) / float64(closed) * 100
	}
	return &s, nil
}

func GetTrades(ctx context.Context, pool *pgxpool.Pool, limit int) ([]Trade, error) {
	rows, err := pool.Query(ctx, `
		SELECT id, symbol, side, leverage, qty, entry_price, exit_price,
		       exit_reason, sl, tp, realized_pnl, fees, opened_ts, closed_ts
		FROM trades ORDER BY opened_ts DESC LIMIT $1`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var trades []Trade
	for rows.Next() {
		var t Trade
		if err := rows.Scan(&t.ID, &t.Symbol, &t.Side, &t.Leverage, &t.Qty,
			&t.EntryPrice, &t.ExitPrice, &t.ExitReason, &t.SL, &t.TP,
			&t.RealizedPnl, &t.Fees, &t.OpenedTs, &t.ClosedTs); err != nil {
			return nil, err
		}
		trades = append(trades, t)
	}
	return trades, nil
}

func GetDecisions(ctx context.Context, pool *pgxpool.Pool, limit int) ([]Decision, error) {
	rows, err := pool.Query(ctx, `
		SELECT correlation_id, agent_name, output, reasoning, confidence, ts
		FROM decisions ORDER BY ts DESC LIMIT $1`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var decisions []Decision
	for rows.Next() {
		var d Decision
		var outputJSON []byte
		if err := rows.Scan(&d.CorrelationID, &d.AgentName, &outputJSON,
			&d.Reasoning, &d.Confidence, &d.Ts); err != nil {
			return nil, err
		}
		d.Output = string(outputJSON)
		decisions = append(decisions, d)
	}
	return decisions, nil
}

func GetMLSignals(ctx context.Context, pool *pgxpool.Pool, limit int) ([]MLSignal, error) {
	rows, err := pool.Query(ctx, `
		SELECT symbol, ts, regime_pred, direction_pred, short_direction,
		       confidence, size_adjustment, model_version
		FROM ml_signals ORDER BY ts DESC LIMIT $1`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var signals []MLSignal
	for rows.Next() {
		var s MLSignal
		if err := rows.Scan(&s.Symbol, &s.Ts, &s.RegimePred, &s.DirectionPred,
			&s.ShortDir, &s.Confidence, &s.SizeAdj, &s.ModelVersion); err != nil {
			return nil, err
		}
		signals = append(signals, s)
	}
	return signals, nil
}

func GetPnlHistory(ctx context.Context, pool *pgxpool.Pool) ([]PnlPoint, error) {
	rows, err := pool.Query(ctx, `
		SELECT closed_ts, realized_pnl,
		       SUM(realized_pnl) OVER (ORDER BY closed_ts) AS cumulative_pnl
		FROM trades
		WHERE closed_ts IS NOT NULL AND realized_pnl IS NOT NULL
		ORDER BY closed_ts`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var points []PnlPoint
	for rows.Next() {
		var p PnlPoint
		if err := rows.Scan(&p.Ts, &p.RealizedPnl, &p.CumulativePnl); err != nil {
			return nil, err
		}
		points = append(points, p)
	}
	return points, nil
}
