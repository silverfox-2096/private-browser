package auth

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/pelletier/go-toml/v2"
)

func pbRead(t *testing.T, document string) (Settings, error) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "auth.toml")
	if err := os.WriteFile(path, []byte(document), 0o600); err != nil {
		t.Fatal(err)
	}
	return Read(path)
}

// Assert behavior independently of diagnostic wording. No production credentials
// or network are used; requests traverse the real auth middleware in memory.
func TestPBConfigRejection(t *testing.T) {
	cases := map[string]struct {
		document string
		strict   bool
	}{
		"unknown_root":     {`unknown = "value"`, true},
		"unknown_role":     {"[[roles]]\nname='client'\nauth='apikey'\napikey='fixture'\nroutes=['GET /v1/vpn/status']\nunknown=true", true},
		"malformed":        {"this is not a toml file", false},
		"duplicate_key":    {"roles=[]\nroles=[]", false},
		"wrong_roles_type": {"roles=42", false},
		"wrong_key_type":   {"[[roles]]\napikey=42", false},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			_, err := pbRead(t, tc.document)
			if err == nil {
				t.Fatal("invalid auth config was accepted")
			}
			if tc.strict {
				var strict *toml.StrictMissingError
				if !errors.As(err, &strict) {
					t.Fatalf("unknown field did not produce strict error: %v", err)
				}
			}
		})
	}
}

func TestPBRoleValidation(t *testing.T) {
	cases := map[string]struct {
		document string
		want     error
	}{
		"missing_apikey": {"[[roles]]\nname='client'\nauth='apikey'\nroutes=['GET /v1/vpn/status']", ErrAPIKeyEmpty},
		"unknown_method": {"[[roles]]\nname='client'\nauth='bogus'\nroutes=['GET /v1/vpn/status']", ErrMethodNotSupported},
		"wrong_route":    {"[[roles]]\nname='client'\nauth='apikey'\napikey='fixture'\nroutes=['GET /invalid']", ErrRoutePathNotSupported},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			settings, err := pbRead(t, tc.document)
			if err != nil {
				t.Fatal(err)
			}
			if err := settings.Validate(); !errors.Is(err, tc.want) {
				t.Fatalf("got %v, want %v", err, tc.want)
			}
		})
	}
}

type pbLogger struct{}

func (pbLogger) Debugf(string, ...any) {}
func (pbLogger) Warnf(string, ...any)  {}

func TestPBParsedConfigAuthorization(t *testing.T) {
	settings, err := pbRead(t, "[[roles]]\nname='client'\nauth='apikey'\napikey='fixture-key'\nroutes=['GET /v1/vpn/status']")
	if err != nil {
		t.Fatal(err)
	}
	want := Settings{Roles: []Role{{Name: "client", Auth: AuthAPIKey, APIKey: "fixture-key", Routes: []string{"GET /v1/vpn/status"}}}}
	if !reflect.DeepEqual(settings, want) {
		t.Fatalf("decoded settings differ: %#v", settings)
	}
	if err := settings.Validate(); err != nil {
		t.Fatal(err)
	}
	middleware, err := New(settings, pbLogger{})
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		name, path, key string
		status          int
	}{
		{"missing_key", "/v1/vpn/status", "", 401},
		{"wrong_key", "/v1/vpn/status", "wrong", 401},
		{"correct_key", "/v1/vpn/status", "fixture-key", 204},
		{"unassigned_route", "/v1/vpn/settings", "fixture-key", 401},
	} {
		t.Run(tc.name, func(t *testing.T) {
			called := false
			handler := middleware(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { called = true; w.WriteHeader(204) }))
			request := httptest.NewRequest(http.MethodGet, tc.path, nil)
			if tc.key != "" {
				request.Header.Set("X-API-Key", tc.key)
			}
			response := httptest.NewRecorder()
			handler.ServeHTTP(response, request)
			if response.Code != tc.status || called != (tc.status == 204) {
				t.Fatalf("status=%d handler_called=%v, want %d", response.Code, called, tc.status)
			}
		})
	}
}
