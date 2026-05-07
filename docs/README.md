# QA Root Cause Analysis Agent

## Overview
A Python-based web application for identifying and analyzing root causes of software defects using:
- 5 Whys analysis
- Fishbone diagram thinking
- Pattern detection
- Impact assessment

## Getting Started
1. Install dependencies:
```bash
pip install flask
```

2. Initialize database:
```python
python -c "from qa_rca_agent.models import init_db; init_db(); print('DB initialized')"
```

3. Run server:
```bash
python qa_rca_agent/app.py
```
Visit http://localhost:5000

## Key Features
- Issue tracking with severity categorization
- Interactive RCA methods:
  - 5 Whys analysis
  - Fishbone diagram
- Pattern analysis and recommendations

## Data Flow
- Capture issue details, severity, and category
- Persist RCA artifacts in SQLite
- Generate 5 Whys, fishbone factors, recommendations, and RCA reports
- Render issue analysis through the Flask UI and JSON API

## Recommended Practices
- Add root causes during issue creation
- Use 5 Whys for pattern detection
- Prioritize recommendations by issue severity and business impact

## Todo
- [ ] Implement browser fuzzing tests
- [ ] Add Jira/GitHub integration
- [ ] Develop severity prediction model
