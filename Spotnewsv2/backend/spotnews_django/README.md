# Spot News 24x7 - Django Reference Backend

This is a clean, isolated Django reference implementation for the MSG91 OTP login flow.
It is intended to serve as a comparison point against the FastAPI backend.

## FastAPI vs Django OTP Flow

### FASTAPI CURRENT SYSTEM
```text
App -> FastAPI -> MSG91 -> Request ID
```

### DJANGO REFERENCE SYSTEM
```text
App -> Django -> MSG91 -> Request ID
```

### Flow Details
- **URL**: `https://api.msg91.com/api/v5/flow/`
- **Method**: `POST`
- **Headers**: `authkey`, `Content-Type: application/json`
- **Payload**:
  ```json
  {
      "flow_id": "<MSG91_TEMPLATE_ID>",
      "sender": "FOUZIA",
      "short_url": "0",
      "recipients": [
          {
              "mobiles": "919346843889",
              "otp": "482913"
          }
      ]
  }
  ```
- **Response**: Expected HTTP 200 with `type: success` and a message containing the request ID.

## Running Instructions

1. **Create virtual environment**:
   `python -m venv venv`
2. **Activate environment**:
   `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
3. **Install dependencies**:
   `pip install -r requirements.txt`
4. **Configure environment**:
   Copy `.env.example` to `.env` and fill in your actual MSG91 auth key.
5. **Run Migrations**:
   `python manage.py makemigrations accounts otp dashboard core`
   `python manage.py migrate`
6. **Create Superuser**:
   `python manage.py createsuperuser`
7. **Run server**:
   `python manage.py runserver`

Access pages at `http://127.0.0.1:8000/`.
