import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Loader2, Clock, CheckCircle, AlertCircle, User, Calendar } from 'lucide-react';
import { format } from 'date-fns';
import { api } from '../api/client';

export default function TaskDetailPage() {
  const { taskId } = useParams();

  const { data: task, isLoading, error } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.getTaskStatus(taskId),
    refetchInterval: (data) => {
      // Stop refetching once completed
      if (data?.status === 'llm_complete' || data?.status === 'completed') {
        return false;
      }
      return 3000; // Refetch every 3 seconds while processing
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card bg-red-50 border border-red-200">
        <div className="flex items-center gap-3">
          <AlertCircle className="w-6 h-6 text-red-600" />
          <div>
            <h3 className="font-semibold text-red-900">Task Not Found</h3>
            <p className="text-red-700">Task ID {taskId} could not be found.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link to="/dashboard" className="inline-flex items-center gap-2 text-primary-600 hover:text-primary-700 mb-4">
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </Link>
        <h1 className="text-3xl font-bold text-gray-900">
          Task #{task.task_id} - SOAP Note
        </h1>
      </div>

      {/* Status Card */}
      <div className="card mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <StatusBadge status={task.status} />
            <div>
              <p className="text-sm text-gray-600">Patient ID</p>
              <p className="font-semibold">{task.patient_id}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Visit Date</p>
              <p className="font-semibold">
                {format(new Date(task.visit_date), 'MMM dd, yyyy HH:mm')}
              </p>
            </div>
          </div>
          <div className="text-right text-sm text-gray-600">
            <p>Created: {format(new Date(task.created_at), 'MMM dd, yyyy HH:mm')}</p>
            <p>Updated: {format(new Date(task.updated_at), 'MMM dd, yyyy HH:mm')}</p>
          </div>
        </div>
      </div>

      {/* SOAP Components */}
      {task.soap_components ? (
        <div className="space-y-4">
          <SOAPSection
            title="Subjective"
            content={task.soap_components.subjective}
            icon={User}
            color="blue"
          />
          <SOAPSection
            title="Objective"
            content={task.soap_components.objective}
            icon={Calendar}
            color="green"
          />
          <SOAPSection
            title="Assessment"
            content={task.soap_components.assessment}
            icon={CheckCircle}
            color="yellow"
          />
          <SOAPSection
            title="Plan"
            content={task.soap_components.plan}
            icon={Clock}
            color="purple"
          />

          {/* Confidence Score */}
          {task.soap_components.confidence_score && (
            <div className="card bg-gray-50">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-700">AI Confidence Score</p>
                  <p className="text-gray-600 text-sm">How confident the AI is in this structuring</p>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-primary-600">
                    {task.soap_components.confidence_score}%
                  </p>
                  <p className="text-sm text-gray-600">
                    {task.soap_components.confidence_score >= 85 ? 'High' :
                     task.soap_components.confidence_score >= 70 ? 'Medium' : 'Low'}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="card bg-yellow-50 border border-yellow-200">
          <div className="flex items-center gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-yellow-600" />
            <div>
              <h3 className="font-semibold text-yellow-900">Processing...</h3>
              <p className="text-yellow-700">AI is structuring your note. This usually takes 5-10 seconds.</p>
            </div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {task.error_message && (
        <div className="card bg-red-50 border border-red-200 mt-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-red-600" />
            <div>
              <h3 className="font-semibold text-red-900">Processing Error</h3>
              <p className="text-red-700">{task.error_message}</p>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      {task.soap_components && (
        <div className="flex gap-3 mt-6">
          <button className="btn btn-primary">
            Send to EMR
          </button>
          <button className="btn btn-secondary">
            Edit SOAP
          </button>
          <button className="btn btn-secondary">
            Copy to Clipboard
          </button>
        </div>
      )}
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

function SOAPSection({ title, content, icon: Icon, color }) {
  const colors = {
    blue: 'bg-blue-50 border-blue-200 text-blue-900',
    green: 'bg-green-50 border-green-200 text-green-900',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-900',
    purple: 'bg-purple-50 border-purple-200 text-purple-900',
  };

  return (
    <div className={`card border ${colors[color]}`}>
      <div className="flex items-start gap-3">
        <Icon className="w-5 h-5 flex-shrink-0 mt-1" />
        <div className="flex-1">
          <h3 className="font-semibold text-lg mb-2">{title}</h3>
          <p className="whitespace-pre-wrap">{content}</p>
        </div>
      </div>
    </div>
  );
}
