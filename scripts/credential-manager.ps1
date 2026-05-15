if (-not (Get-Variable -Name GoodNewsCredentialManagerLoaded -Scope Script -ErrorAction SilentlyContinue)) {
    $script:GoodNewsCredentialManagerLoaded = $false
}
$script:GoodNewsCredentialManagerLoaded = $script:GoodNewsCredentialManagerLoaded -eq $true

if (-not $script:GoodNewsCredentialManagerLoaded) {
    Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

namespace GoodNews {
    public static class CredentialManager {
        private const int CRED_TYPE_GENERIC = 1;
        private const int CRED_PERSIST_LOCAL_MACHINE = 2;
        private const int ERROR_NOT_FOUND = 1168;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct CREDENTIAL {
            public int Flags;
            public int Type;
            public string TargetName;
            public string Comment;
            public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
            public int CredentialBlobSize;
            public IntPtr CredentialBlob;
            public int Persist;
            public int AttributeCount;
            public IntPtr Attributes;
            public string TargetAlias;
            public string UserName;
        }

        [DllImport("Advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CredRead(string target, int type, int reservedFlag, out IntPtr credentialPtr);

        [DllImport("Advapi32.dll", EntryPoint = "CredWriteW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CredWrite(ref CREDENTIAL userCredential, int flags);

        [DllImport("Advapi32.dll", SetLastError = true)]
        private static extern void CredFree(IntPtr credentialPtr);

        public static bool Exists(string targetName) {
            string ignored;
            return TryGetSecret(targetName, out ignored);
        }

        public static string GetSecret(string targetName) {
            string secret;
            if (TryGetSecret(targetName, out secret)) {
                return secret;
            }

            throw new InvalidOperationException(string.Format("Credential '{0}' was not found.", targetName));
        }

        public static void SetSecret(string targetName, string secret) {
            var bytes = Encoding.Unicode.GetBytes(secret);
            var credential = new CREDENTIAL {
                Type = CRED_TYPE_GENERIC,
                TargetName = targetName,
                CredentialBlobSize = bytes.Length,
                Persist = CRED_PERSIST_LOCAL_MACHINE,
                UserName = "good-news"
            };

            credential.CredentialBlob = Marshal.AllocCoTaskMem(bytes.Length);

            try {
                Marshal.Copy(bytes, 0, credential.CredentialBlob, bytes.Length);

                if (!CredWrite(ref credential, 0)) {
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                }
            }
            finally {
                Marshal.FreeCoTaskMem(credential.CredentialBlob);
            }
        }

        private static bool TryGetSecret(string targetName, out string secret) {
            secret = null;
            IntPtr credentialPtr;
            if (!CredRead(targetName, CRED_TYPE_GENERIC, 0, out credentialPtr)) {
                var error = Marshal.GetLastWin32Error();
                if (error == ERROR_NOT_FOUND) {
                    return false;
                }

                throw new Win32Exception(error);
            }

            try {
                var credential = Marshal.PtrToStructure<CREDENTIAL>(credentialPtr);
                var bytes = new byte[credential.CredentialBlobSize];
                Marshal.Copy(credential.CredentialBlob, bytes, 0, credential.CredentialBlobSize);
                secret = Encoding.Unicode.GetString(bytes);
                return true;
            }
            finally {
                CredFree(credentialPtr);
            }
        }
    }
}
"@

    $script:GoodNewsCredentialManagerLoaded = $true
}

if (-not (Get-Command -Name Get-GoodNewsCredentialValue -ErrorAction SilentlyContinue -CommandType Function)) {
    function Get-GoodNewsCredentialValue {
        param(
            [Parameter(Mandatory)]
            [string]$TargetName
        )

        [GoodNews.CredentialManager]::GetSecret($TargetName)
    }
}

if (-not (Get-Command -Name Set-GoodNewsCredentialValue -ErrorAction SilentlyContinue -CommandType Function)) {
    function Set-GoodNewsCredentialValue {
        param(
            [Parameter(Mandatory)]
            [string]$TargetName,
            [Parameter(Mandatory)]
            [string]$Secret
        )

        [GoodNews.CredentialManager]::SetSecret($TargetName, $Secret)
    }
}

if (-not (Get-Command -Name Test-GoodNewsCredentialExists -ErrorAction SilentlyContinue -CommandType Function)) {
    function Test-GoodNewsCredentialExists {
        param(
            [Parameter(Mandatory)]
            [string]$TargetName
        )

        [GoodNews.CredentialManager]::Exists($TargetName)
    }
}
