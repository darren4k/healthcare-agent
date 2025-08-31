# Healthcare Agent

## 🎯 Project Vision

Healthcare Agent is a cutting-edge automation MVP designed to revolutionize healthcare workflows through intelligent automation and comprehensive testing frameworks. Our platform combines the power of Playwright automation with robust data management and audit capabilities to ensure reliable, secure, and efficient healthcare operations.

### Key Goals
- **Streamline Healthcare Workflows**: Automate repetitive tasks to allow healthcare professionals to focus on patient care
- **Ensure Compliance**: Built-in audit trails and logging for healthcare regulatory compliance
- **Maximize Reliability**: Comprehensive testing framework to ensure system reliability and data integrity
- **Enable Scalability**: Modular architecture supporting rapid development and deployment

## 🏗️ Architecture

```
healthcare-agent/
├── backend/              # Core application logic
├── automation/
│   └── playwright/       # Playwright test automation
├── data/
│   ├── logs/            # Application and audit logs
│   └── test_data/       # Test datasets and fixtures
├── config/              # Configuration files
├── docs/                # Documentation
└── feedback/            # User feedback and analytics
```

## 🚀 Quick Setup

### Prerequisites
- Python 3.9+
- Node.js 16+
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/darren4k/healthcare-agent.git
   cd healthcare-agent
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Install Playwright dependencies**
   ```bash
   cd automation/playwright
   npm install
   npx playwright install
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run initial setup**
   ```bash
   python backend/setup.py
   ```

### Running the Application

```bash
# Start the backend service
python backend/main.py

# Run automation tests
cd automation/playwright
npm test

# Run audit analysis
python audit.py
```

## 🧪 Testing

- **Unit Tests**: `pytest backend/tests/`
- **Integration Tests**: `pytest automation/tests/`
- **E2E Tests**: `npm test` in automation/playwright/

## 📊 Monitoring & Audit

- Logs are stored in `data/logs/`
- Audit trails are generated automatically
- Run `python audit.py` for compliance reports

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For questions and support, please:
- Check the documentation in `docs/`
- Submit feedback via `feedback/`
- Open an issue on GitHub

---

**Built with ❤️ for healthcare innovation**
