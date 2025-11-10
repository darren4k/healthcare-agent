import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { FileText, Home, LayoutDashboard, Activity, UserPlus } from 'lucide-react';
import SubmitPage from './pages/SubmitPage';
import DashboardPage from './pages/DashboardPage';
import TaskDetailPage from './pages/TaskDetailPage';
import LiveTasksPage from './pages/LiveTasksPage';
import PatientIntakePage from './pages/PatientIntakePage';
import IntakeConfirmationPage from './pages/IntakeConfirmationPage';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        {/* Navigation */}
        <nav className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center space-x-8">
                <Link to="/" className="flex items-center space-x-2">
                  <FileText className="w-6 h-6 text-primary-600" />
                  <span className="text-xl font-bold text-gray-900">
                    Agentic SOAP
                  </span>
                </Link>
                <div className="flex space-x-4">
                  <NavLink to="/" icon={Home} label="Submit Note" />
                  <NavLink to="/dashboard" icon={LayoutDashboard} label="Dashboard" />
                  <NavLink to="/live-tasks" icon={Activity} label="Live Tasks" />
                  <NavLink to="/patient-intake" icon={UserPlus} label="Patient Intake" />
                </div>
              </div>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Routes>
            <Route path="/" element={<SubmitPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
            <Route path="/live-tasks" element={<LiveTasksPage />} />
            <Route path="/patient-intake" element={<PatientIntakePage />} />
            <Route path="/intake-confirmation/:intakeId" element={<IntakeConfirmationPage />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-gray-200 mt-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <p className="text-center text-gray-500 text-sm">
              Agentic SOAP Note System v1.0.0 | HIPAA Compliant
            </p>
          </div>
        </footer>
      </div>
    </BrowserRouter>
  );
}

function NavLink({ to, icon: Icon, label }) {
  return (
    <Link
      to={to}
      className="flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-primary-600 hover:bg-gray-100 transition-colors"
    >
      <Icon className="w-4 h-4" />
      <span>{label}</span>
    </Link>
  );
}

export default App;
