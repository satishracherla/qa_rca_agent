# QA Agent for Root Cause Analysis

A Python-based web application that helps identify and analyze root causes of issues in software development and QA processes.

## Features

- **Issue Management**: Create, track, and manage issues
- **Root Cause Analysis**: Automated and manual RCA techniques including:
  - 5 Whys Analysis
  - Fishbone (Ishikawa) Diagram
  - Pareto Analysis
- **Pattern Detection**: Identify recurring issues and patterns
- **Impact Assessment**: Evaluate severity and business impact
- **Recommendation Engine**: Suggest preventive measures

## Tech Stack

- Backend: Python with Flask
- Frontend: HTML, CSS, JavaScript
- Database: SQLite (file-based, no setup required)

## Installation

```bash
pip install flask
```

## Usage

```bash
python app.py
```

Then open http://localhost:5000 in your browser.

## Project Structure

```
qa_rca_agent/
├── app.py                 # Main Flask application
├── models.py              # Data models
├── analyzer.py           # RCA algorithms
├── static/
│   ├── css/
│   │   └── style.css      # Styles
│   └── js/
│       └── main.js       # Frontend logic
└── templates/
    └── index.html        # Main UI
