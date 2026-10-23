package local

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestCompressionCompatibility(t *testing.T) {
	for _, role := range []string{"A", "C"} {
		data, err := os.ReadFile(filepath.Join(os.Getenv("PERF391_LOGGING_CONFIGS"), role+".compose.json"))
		if err != nil {
			t.Fatal(err)
		}
		var config struct {
			Services map[string]struct {
				Logging struct {
					Driver  string
					Options map[string]string
				}
			}
		}
		if err := json.Unmarshal(data, &config); err != nil {
			t.Fatal(err)
		}
		if len(config.Services) != 3 {
			t.Fatal("expected three diagnostic services")
		}
		for name, service := range config.Services {
			t.Run(role+"/"+name, func(t *testing.T) {
				if service.Logging.Driver != "local" {
					t.Fatal("unexpected driver")
				}
				opts := service.Logging.Options
				cfg, err := newConfig(opts)
				if err != nil {
					t.Fatal(err)
				}
				if cfg.MaxFileSize != 10000000 || cfg.MaxFileCount != 1 || !cfg.DisableCompression {
					t.Fatalf("unbounded or compressed config: %+v", cfg)
				}
				for _, mode := range []string{"omitted", "true"} {
					bad := make(map[string]string)
					for k, v := range opts {
						bad[k] = v
					}
					if mode == "omitted" {
						delete(bad, "compress")
					} else {
						bad["compress"] = mode
					}
					_, err := newConfig(bad)
					if err == nil || err.Error() != "compression cannot be enabled when max file count is 1" {
						t.Fatalf("%s: expected original startup rejection, got %v", mode, err)
					}
				}
				bad := map[string]string{"max-size": "10m", "max-file": "1", "compress": "invalid"}
				if _, err := newConfig(bad); err == nil {
					t.Fatal("invalid boolean accepted")
				}
				t.Log("corrected config accepted; omitted/default and explicit true rejected; invalid boolean rejected")
			})
		}
	}
}
