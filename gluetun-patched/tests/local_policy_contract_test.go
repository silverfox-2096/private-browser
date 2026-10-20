package firewall

import (
 "context"
 "errors"
 "os"
 "os/exec"
 "path/filepath"
 "testing"

 "github.com/golang/mock/gomock"
 "github.com/stretchr/testify/require"
)

// These tests document the real pinned optional loader; they do not replace the
// host kernel assertion. In particular, absent/empty/unrecognized files can return nil.
func TestPBLocalPolicyLoaderContract(t *testing.T) {
 sentinel := errors.New("iptables rejected invalid instruction")
 for _, tc := range []struct {
  name, text string
  missing, noIPv6, rejectCommand bool
  wantCalls int
  wantError bool
 }{
  {name:"missing optional file", missing:true},
  {name:"empty optional file"},
  {name:"unrecognized line ignored", text:"not-iptables malformed\n"},
  {name:"recognized valid instruction", text:"iptables -I OUTPUT 1 -j REJECT\n", wantCalls:1},
  {name:"recognized command error propagated", text:"iptables --invalid-option\n", rejectCommand:true, wantCalls:1, wantError:true},
  {name:"missing IPv6 implementation rejected", text:"ip6tables -I OUTPUT 1 -j REJECT\n", noIPv6:true, wantError:true},
 } {
  t.Run(tc.name, func(t *testing.T) {
   path := filepath.Join(t.TempDir(), "post-rules.txt")
   if !tc.missing { require.NoError(t, os.WriteFile(path, []byte(tc.text), 0o600)) }
   ctrl := gomock.NewController(t)
   logger := NewMockLogger(ctrl)
   logger.EXPECT().Debug(gomock.Any()).AnyTimes()
   runner := NewMockCmdRunner(ctrl)
   if tc.wantCalls > 0 {
    runner.EXPECT().Run(gomock.Any()).DoAndReturn(func(_ *exec.Cmd)(string,error) {
     if tc.rejectCommand { return "invalid option", sentinel }; return "",nil
    }).Times(tc.wantCalls)
   }
   c := &Config{runner:runner, logger:logger, ipTables:"iptables", ip6Tables:"ip6tables"}
   if tc.noIPv6 { c.ip6Tables="" }
   err := c.runUserPostRules(context.Background(), path, false)
   if tc.wantError { require.Error(t,err) } else { require.NoError(t,err) }
  })
 }
}
