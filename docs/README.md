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
python app.py
```
Visit http://localhost:5000

## Key Features
- Issue tracking with severity categorization
- Interactive RCA methods:
  - [5 Whys analysis](analysis.html#5-whys)
  - [Fishbone diagram](analysis.html#fishbone)
- Pattern analysis and recommendations

## Data Flow
![Data Flow](docs/flow.png)

## Recommended Practices
- Add root causes during issue creation
- Use 5 Whys for pattern detection
- Prioritize recommendations by confusion matrix accuracy

## Todo
- [ ] Implement browser fuzzing tests
- [ ] Add Jira/GitHub integration
- [ ] Develop severity prediction model
