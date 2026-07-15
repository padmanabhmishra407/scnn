# SCNN - Self-Improving Cybernetic Neural Network Research Project

## Identity
Neuroscience and cybernetics research project focused on adaptive systems, self-improving architectures, and cognitive modeling. Working with neural networks that learn from their environment and improve over time through feedback loops.

## Development Philosophy
**Learn as you build.** This isn't a linear development process — it's an iterative learning system where each experiment teaches the next one. Mistakes are data points for improvement. Documentation is part of the codebase, not separate artifacts.

## Tool Usage Policy
- **Use Codex for deep investigation**: debugging, verification, second implementation passes
- **Methodical work only**: no shortcuts or compacted reasoning — tools first, conclusions second
- **Self-improvement loop**: when stuck → investigate thoroughly → learn pattern → apply to next similar problem

## Project Structure (Minimal)
```
/Users/padmanabhmishra/Documents/scnn/
├── CLAUDE.md          # ← you are here, evolve this as project grows
├── .gitignore         # comprehensive Python + ML research ignores
├── requirements.txt   # pinned dependencies
├── pyproject.toml     # project metadata and build config
└── src/               # core code (create only when needed)
    ├── models/        # neural network architectures
    ├── preprocessing/ # data pipeline functions
    └── analysis/      # experimental results processing
```

## Self-Improvement Patterns
### When Debugging
1. Use Codex rescue agent for root cause investigation
2. Document the failure pattern in memory if it's novel
3. Update relevant tools or scripts to prevent recurrence
4. Verify fix works end-to-end before marking complete

### When Learning New Techniques
1. Explore thoroughly with agents before coding
2. Build minimal working example first
3. Document findings in CLAUDE.md or a dedicated note
4. Reuse patterns across projects when applicable

## Research Focus Areas (Add as project evolves)
- Self-improving neural architectures
- Cybernetic systems with feedback loops
- Neuroscience-inspired computation models
- Adaptive learning systems
- Cognitive architecture research

## Environment Setup
Use `python -m venv .venv` and `pip install -r requirements.txt`. Activate with `.venv/bin/activate` (macOS/Linux) or `.venv\Scripts\activate` (Windows). Never commit the virtual environment — it's in `.gitignore`.

## Virtual HID Integration
A virtual HID device was previously built using PyObjC to register an IOKit HID service on macOS, allowing programmatic injection of input events directly into the OS as if from real hardware. This bypasses UI scripting / accessibility API limitations for direct machine interaction. See memory `[[virtual-hid-integration]]` for details and rebuild instructions.
