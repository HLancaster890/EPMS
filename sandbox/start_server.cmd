@echo off
SET EPMS_DEV_MODE=true
SET EPMS_DEV_CREDENTIALS=eyJlbWFpbCI6ImFkbWluQGNvcnAubG9jYWwiLCJwYXNzd29yZCI6Ik15UEBzczEiLCJyb2xlIjoic3VwZXJfYWRtaW4iLCJvcmdfaWQiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDAiLCJkaXNwbGF5X25hbWUiOiJBZG1pbmlzdHJhdG9yIn0=
SET JWT_SECRET=super-secret-key-change-in-production-2024
cd /d "D:\activitywatch\activitywatch_Source code\epms-server-installer\Resources\services"
"C:\Program Files\Python314\python.exe" -m uvicorn epms_server_service:app --host 0.0.0.0 --port 8000
