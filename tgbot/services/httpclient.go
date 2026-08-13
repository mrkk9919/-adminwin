package services

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// HTTPClient is a reusable HTTP client with timeout and retry support
// for making external API calls.
type HTTPClient struct {
	client  *http.Client
	baseURL string
	apiKey  string
	retries int
}

// Option configures the HTTPClient.
type Option func(*HTTPClient)

// WithTimeout sets the HTTP request timeout.
func WithTimeout(d time.Duration) Option {
	return func(c *HTTPClient) {
		c.client.Timeout = d
	}
}

// WithRetries sets the number of retry attempts for failed requests.
func WithRetries(n int) Option {
	return func(c *HTTPClient) {
		c.retries = n
	}
}

// WithAPIKey sets the API key for request authentication.
func WithAPIKey(key string) Option {
	return func(c *HTTPClient) {
		c.apiKey = key
	}
}

// NewHTTPClient creates a new HTTPClient with the given base URL and options.
func NewHTTPClient(baseURL string, opts ...Option) *HTTPClient {
	c := &HTTPClient{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		baseURL: baseURL,
		retries: 2,
	}
	for _, opt := range opts {
		opt(c)
	}
	return c
}

// Get performs a GET request to the specified path and decodes the JSON response
// into the provided target. The path is appended to the base URL.
func (c *HTTPClient) Get(ctx context.Context, path string, target interface{}) error {
	url := c.baseURL + path

	var lastErr error
	for attempt := 0; attempt <= c.retries; attempt++ {
		if attempt > 0 {
			// Exponential backoff: 1s, 2s, 4s...
			backoff := time.Duration(1<<uint(attempt-1)) * time.Second
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(backoff):
			}
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if err != nil {
			return fmt.Errorf("creating request: %w", err)
		}

		if c.apiKey != "" {
			req.Header.Set("Authorization", "Bearer "+c.apiKey)
		}
		req.Header.Set("Accept", "application/json")

		resp, err := c.client.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("executing request: %w", err)
			continue
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()

		if resp.StatusCode >= 500 {
			lastErr = fmt.Errorf("server error: status %d", resp.StatusCode)
			continue
		}

		if err != nil {
			return fmt.Errorf("reading response: %w", err)
		}

		if resp.StatusCode >= 400 {
			return fmt.Errorf("API error: status %d, body: %s", resp.StatusCode, string(body))
		}

		if target != nil {
			if err := json.Unmarshal(body, target); err != nil {
				return fmt.Errorf("decoding response: %w", err)
			}
		}

		return nil
	}

	return fmt.Errorf("request failed after %d attempts: %w", c.retries+1, lastErr)
}

// GetRaw performs a GET request and returns the raw response body as a string.
func (c *HTTPClient) GetRaw(ctx context.Context, path string) (string, error) {
	var raw json.RawMessage
	if err := c.Get(ctx, path, &raw); err != nil {
		return "", err
	}
	return string(raw), nil
}
