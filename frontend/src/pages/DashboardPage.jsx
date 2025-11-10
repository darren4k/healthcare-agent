import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Search, Eye, Calendar, User } from 'lucide-react';
import { format } from 'date-fns';
import { api } from '../api/client';

export default function DashboardPage() {
  const [search, setSearch] = useState('');

  // For now, we'll use a mock endpoint since getAllTasks isn't implemented yet
  // In production, this would fetch from /api/tasks
  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: async () => {
      // Mock data - replace with api.getAllTasks() once backend endpoint exists
      return [];
    },
    refetchInterval: 10000, // Refetch every 10 seconds
  });

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  const filteredTasks = tasks?.filter(task =>
    task.patient_id.toLowerCase().includes(search.toLowerCase())
  ) || [];

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-2">
          View and manage submitted SOAP notes
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Total Notes"
          value={tasks?.length || 0}
          color="blue"
        />
        <StatCard
          label="Processing"
          value={tasks?.filter(t => t.status === 'processing').length || 0}
          color="yellow"
        />
        <StatCard
          label="Completed"
          value={tasks?.filter(t => t.status === 'llm_complete' || t.status === 'completed').length || 0}
          color="green"
        />
        <StatCard
          label="Failed"
          value={tasks?.filter(t => t.status === 'failed').length || 0}
          color="red"
        />
      </div>

      {/* Search */}
      <div className="card mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search by patient ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>
      </div>

      {/* Tasks Table */}
      {filteredTasks.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-gray-600">No notes found. Start by submitting a note!</p>
          <Link to="/" className="btn btn-primary mt-4 inline-block">
            Submit Note
          </Link>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Task ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Patient
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Visit Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Confidence
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Submitted
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredTasks.map((task) => (
                <tr key={task.task_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    #{task.task_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {task.patient_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4" />
                      {format(new Date(task.visit_date), 'MMM dd, yyyy')}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <StatusBadge status={task.status} />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {task.soap_components?.confidence_score ? (
                      <span className="font-medium">
                        {task.soap_components.confidence_score}%
                      </span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {format(new Date(task.created_at), 'MMM dd, HH:mm')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                    <Link
                      to={`/tasks/${task.task_id}`}
                      className="inline-flex items-center gap-1 text-primary-600 hover:text-primary-700"
                    >
                      <Eye className="w-4 h-4" />
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
  };

  return (
    <div className={`card ${colors[color]}`}>
      <p className="text-sm font-medium opacity-80">{label}</p>
      <p className="text-3xl font-bold mt-2">{value}</p>
    </div>
  );
}

function StatusBadge({ status }) {
  const config = {
    pending: { label: 'Pending', className: 'badge badge-info' },
    processing: { label: 'Processing', className: 'badge badge-warning' },
    llm_complete: { label: 'Complete', className: 'badge badge-success' },
    completed: { label: 'Completed', className: 'badge badge-success' },
    failed: { label: 'Failed', className: 'badge badge-error' },
  };

  const { label, className } = config[status] || config.pending;
  return <span className={className}>{label}</span>;
}
