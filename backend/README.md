# ⚡ DataVista Backend API (FastAPI, Pandas & Seaborn)

High-performance asynchronous **FastAPI** REST API service for uploaded CSV analytics, Pandas/NumPy data manipulation, and in-memory Seaborn chart visualization.

---

## 🏗️ Architecture & File Split

The backend is cleanly split into two dedicated modules:

```
backend/
├── api.py              # FastAPI application, Uvicorn server, upload & auto-cleanup endpoints
├── analysis.py         # Pandas/NumPy data engine & in-memory Seaborn visualization
├── requirements.txt    # Python dependencies (FastAPI, Uvicorn, Pandas, Seaborn, Matplotlib)
├── uploads/            # Temporary directory for active user CSV files
└── venv/               # Python virtual environment
```

### 1. `api.py` (FastAPI Controller)
- Built with **FastAPI** and **Pydantic** request validation.
- Configured with `CORSMiddleware` to communicate with the frontend.
- Receives file uploads using `UploadFile = File(...)` and writes to `backend/uploads/` with UUID-prefixed filenames.
- Coordinates calls to `analysis.py` for CSV parsing and chart generation.
- Handles automatic server-side file deletion on page refresh (`/api/cleanup`).

### 2. `analysis.py` (Data & Visualization Engine)
- **Pandas & NumPy**: Reads uploaded CSV, extracts column names, identifies numeric vs. categorical types, and calculates statistics (Mean, Median, Sum, Std Dev, Min, Max).
- **Seaborn & Matplotlib**: Generates high-DPI styled charts (Dark & Light theme aware).
- **In-Memory Streaming**: Captured strictly in an `io.BytesIO()` memory buffer and converted to Base64 bytes. **Zero image files are ever stored on disk**.

---

## 🚀 Setup & Execution

### Prerequisites
- Python 3.10+ (Tested on Python 3.12)
- Virtual environment (`venv`)

### 1. Virtual Environment & Dependencies
```bash
cd backend
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

### 2. Run Backend Server with Uvicorn
```bash
./venv/bin/uvicorn api:app --host 0.0.0.0 --port 5000
```
*The FastAPI backend will start at:* **`http://127.0.0.1:5000`**

*Interactive Swagger API Docs available at:* **`http://127.0.0.1:5000/docs`**

---

## 📡 API Endpoints

### 1. Health Check
- **Endpoint**: `GET /api/health`
- **Response**:
```json
{
  "status": "success",
  "message": "DataVista FastAPI Backend (api.py + analysis.py) is active and ready for CSV uploads.",
  "framework": "FastAPI",
  "version": "3.0.0"
}
```

---

### 2. Upload CSV File
- **Endpoint**: `POST /api/upload`
- **Content-Type**: `multipart/form-data`
- **Body**: `file: <your_file.csv>`
- **Response**:
```json
{
  "status": "success",
  "filename": "a8f3b19c_sales_data.csv",
  "display_name": "sales_data.csv",
  "file_size": 528,
  "total_rows": 15,
  "total_columns": 6,
  "missing_values": 0,
  "columns": ["Product", "Region", "Month", "SalesAmount", "Profit", "UnitsSold"],
  "numeric_columns": ["SalesAmount", "Profit", "UnitsSold"],
  "categorical_columns": ["Product", "Region", "Month"],
  "preview_data": [ ... ]
}
```

---

### 3. Generate Chart (In-Memory Bytes Stream)
- **Endpoint**: `POST /api/visualize`
- **Content-Type**: `application/json`
- **Request Body**:
```json
{
  "filename": "a8f3b19c_sales_data.csv",
  "x_axis": "Product",
  "y_axis": "Profit",
  "chart_type": "pie",
  "palette": "berry",
  "theme": "dark"
}
```
- **Response**:
```json
{
  "status": "success",
  "chart_title": "Profit by Product (PIE)",
  "engine": "Pandas + NumPy + Seaborn (In-Memory Bytes Stream)",
  "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAwg...",
  "labels": ["Laptop", "SmartPhone", "Tablet", ...],
  "values": [3400.0, 2350.0, 1300.0, ...],
  "summary_stats": {
    "total_sum": 23470.0,
    "mean": 1564.6,
    "median": 1150.0,
    "std_dev": 892.4,
    "min": 650.0,
    "max": 3400.0,
    "count": 15
  }
}
```

---

### 4. Delete Uploaded File (Auto Cleanup)
- **Endpoint**: `POST /api/cleanup`
- **Content-Type**: `application/json`
- **Request Body**:
```json
{
  "filename": "a8f3b19c_sales_data.csv"
}
```
- **Response**:
```json
{
  "status": "success",
  "message": "File a8f3b19c_sales_data.csv deleted from server"
}
```

---

## 🛡️ Key Features & Safeguards

1. **Pure FastAPI Async Architecture**: Built with asynchronous request handling and Pydantic validation.
2. **Strictly Upload-Driven**: No hardcoded static datasets. All queries are executed directly on the user's uploaded file.
3. **RAM-Only Visuals**: Matplotlib figures are closed immediately after streaming bytes (`plt.close('all')`), guaranteeing no file system clutter and no memory leaks.
4. **Auto-Clean on Refresh**: Paired with the frontend's `beforeunload` beacon to instantly delete temporary files from the disk when a user reloads or closes the page.
