$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\frontend")
node --version
npm --version
npm install
npm run lint
npm run typecheck
npm run build
npm run dev
