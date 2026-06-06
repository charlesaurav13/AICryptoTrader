package grpcclient

import (
	"context"
	"time"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	pb "cryptoswarm/go-backend/proto"
)

type Client struct {
	conn *grpc.ClientConn
	svc  pb.TradingServiceClient
}

func New(addr string) (*Client, error) {
	conn, err := grpc.NewClient(addr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return nil, err
	}
	return &Client{conn: conn, svc: pb.NewTradingServiceClient(conn)}, nil
}

func (c *Client) Close() {
	if c != nil && c.conn != nil {
		c.conn.Close()
	}
}

func (c *Client) GetLivePositions(ctx context.Context) (*pb.PositionsResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	return c.svc.GetLivePositions(ctx, &pb.Empty{})
}

func (c *Client) GetAgentStatus(ctx context.Context) (*pb.AgentStatusResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	return c.svc.GetAgentStatus(ctx, &pb.Empty{})
}
