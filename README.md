# SCNN - Self-Improving Cybernetic Neural Network

## Project Overview
A neuroscience and cybernetics research project focused on building adaptive systems that learn from their environment and improve over time through feedback loops.

## Getting Started

### Prerequisites
- Python 3.9+ (verify with `python3 --version`)
- GitHub CLI (`gh`) installed for repository operations
- Codex CLI available for tool-based verification

### Environment Setup
```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate  # macOS/Linux
# or: .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Self-Improvement Loop

This project uses Codex for deep investigation when building adaptive systems. The pattern:

1. **Identify problem** → Write minimal reproduction script in `src/`
2. **Investigate with Codex** → Use `/codex:task` or `codex-rescue` agent for root cause analysis
3. **Learn pattern** → Document findings in memory if novel failure mode
4. **Verify fix** → Run end-to-end test before marking complete

## Directory Structure
```
/Users/padmanabhmishra/Documents/scnn/
├── CLAUDE.md          # Project context and development philosophy
├── README.md          # ← you are here, setup instructions
├── requirements.txt   # Pinned dependencies for reproducibility
├── pyproject.toml     # Project metadata and build configuration
└── src/               # Core code (create as needed)
    ├── models/        # Neural network architectures
    ├── preprocessing/ # Data pipeline functions
    └── analysis/      # Experimental results processing
```

## Research Focus Areas
- Self-improving neural architectures with feedback loops
- Cybernetic systems that adapt to environment changes
- Neuroscience-inspired computation models
- Adaptive learning algorithms for cognitive tasks
