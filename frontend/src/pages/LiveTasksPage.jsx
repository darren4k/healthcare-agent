import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PlayIcon, StopIcon, EyeIcon, VideoCameraIcon, DocumentArrowDownIcon } from '@heroicons/react/24/outline';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
const WS_BASE_URL = API_BASE_URL.replace('http', 'ws');

export default function LiveTasksPage() {
  const [activeTasks, setActiveTasks] = useState(new Map());
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const wsRef = useRef(null);

  // Fetch all tasks
  const { data: tasks } = useQuery({
    queryKey: ['tasks'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/tasks`);
      if (!response.ok) throw new Error('Failed to fetch tasks');
      return response.json();
    },
    refetchInterval: 5000, // Refetch every 5 seconds
  });

  // WebSocket connection for real-time updates
  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE_URL}/ws/tasks`);

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('WebSocket message:', message);

      setActiveTasks((prev) => {
        const next = new Map(prev);
        const taskId = message.task_id;

        if (!taskId) return prev;

        // Get existing task data or create new
        const taskData = next.get(taskId) || {
          task_id: taskId,
          status: 'unknown',
          current_step: 0,
          total_steps: 0,
          progress: 0,
          screenshot_url: null,
          error: null,
          events: [],
        };

        // Update based on event type
        switch (message.event) {
          case 'task_started':
            taskData.status = 'running';
            taskData.total_steps = message.total_steps;
            taskData.patient_id = message.patient_id;
            taskData.events.push({ type: 'started', timestamp: message.timestamp });
            break;

          case 'step_started':
            taskData.current_step = message.step_number;
            taskData.progress = message.progress || 0;
            taskData.current_action = message.action;
            taskData.current_description = message.description;
            taskData.events.push({
              type: 'step_started',
              step: message.step_number,
              action: message.action,
              description: message.description,
              timestamp: message.timestamp,
            });
            break;

          case 'step_completed':
            taskData.progress = message.progress || 0;
            if (message.screenshot_url) {
              taskData.screenshot_url = `${API_BASE_URL}${message.screenshot_url}`;
            }
            taskData.events.push({
              type: 'step_completed',
              step: message.step_number,
              screenshot: message.screenshot_url,
              timestamp: message.timestamp,
            });
            break;

          case 'step_failed':
            taskData.error = message.error;
            if (message.screenshot_url) {
              taskData.screenshot_url = `${API_BASE_URL}${message.screenshot_url}`;
            }
            taskData.events.push({
              type: 'step_failed',
              step: message.step_number,
              error: message.error,
              screenshot: message.screenshot_url,
              timestamp: message.timestamp,
            });
            break;

          case 'task_completed':
            taskData.status = message.success ? 'completed' : 'failed';
            taskData.progress = 100;
            taskData.confidence = message.confidence;
            taskData.emr_url = message.emr_url;
            taskData.video_url = message.video_url
              ? `${API_BASE_URL}${message.video_url}`
              : null;
            taskData.trace_url = message.trace_url
              ? `${API_BASE_URL}${message.trace_url}`
              : null;
            taskData.events.push({
              type: 'completed',
              success: message.success,
              timestamp: message.timestamp,
            });
            break;

          case 'recovery_started':
            taskData.events.push({
              type: 'recovery',
              attempt: message.attempt,
              strategy: message.strategy,
              reason: message.reason,
              timestamp: message.timestamp,
            });
            break;
        }

        next.set(taskId, taskData);
        return next;
      });
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };

    // Send ping every 30 seconds to keep connection alive
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 30000);

    wsRef.current = ws;

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, []);

  const activeTasksList = Array.from(activeTasks.values()).filter(
    (task) => task.status === 'running'
  );

  const completedTasksList = Array.from(activeTasks.values()).filter(
    (task) => task.status === 'completed' || task.status === 'failed'
  );

  const selectedTask = selectedTaskId ? activeTasks.get(selectedTaskId) : null;

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Live Task Monitoring</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Task List */}
          <div className="lg:col-span-1 space-y-4">
            {/* Active Tasks */}
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-xl font-semibold mb-4 flex items-center">
                <PlayIcon className="h-5 w-5 mr-2 text-green-500" />
                Active Tasks ({activeTasksList.length})
              </h2>
              <div className="space-y-2">
                {activeTasksList.length === 0 ? (
                  <p className="text-gray-500 text-sm">No active tasks</p>
                ) : (
                  activeTasksList.map((task) => (
                    <button
                      key={task.task_id}
                      onClick={() => setSelectedTaskId(task.task_id)}
                      className={`w-full text-left p-3 rounded-lg border transition-colors ${
                        selectedTaskId === task.task_id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-medium">Task #{task.task_id}</span>
                        <span className="text-xs text-gray-500">
                          {task.current_step}/{task.total_steps}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${task.progress}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-600 truncate">
                        {task.current_description || 'Processing...'}
                      </p>
                    </button>
                  ))
                )}
              </div>
            </div>

            {/* Completed Tasks */}
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-xl font-semibold mb-4 flex items-center">
                <StopIcon className="h-5 w-5 mr-2 text-gray-500" />
                Recent Completed ({completedTasksList.length})
              </h2>
              <div className="space-y-2">
                {completedTasksList.slice(0, 5).map((task) => (
                  <button
                    key={task.task_id}
                    onClick={() => setSelectedTaskId(task.task_id)}
                    className={`w-full text-left p-3 rounded-lg border transition-colors ${
                      selectedTaskId === task.task_id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-medium">Task #{task.task_id}</span>
                      <span
                        className={`text-xs px-2 py-1 rounded ${
                          task.status === 'completed'
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {task.status}
                      </span>
                    </div>
                    {task.confidence && (
                      <p className="text-xs text-gray-600 mt-1">
                        Confidence: {task.confidence}%
                      </p>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Task Details */}
          <div className="lg:col-span-2">
            {selectedTask ? (
              <div className="bg-white shadow rounded-lg p-6">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-2xl font-semibold">
                    Task #{selectedTask.task_id}
                  </h2>
                  <span
                    className={`px-3 py-1 rounded-full text-sm font-medium ${
                      selectedTask.status === 'running'
                        ? 'bg-blue-100 text-blue-800'
                        : selectedTask.status === 'completed'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {selectedTask.status}
                  </span>
                </div>

                {/* Progress */}
                {selectedTask.status === 'running' && (
                  <div className="mb-6">
                    <div className="flex justify-between text-sm text-gray-600 mb-2">
                      <span>
                        Step {selectedTask.current_step} of {selectedTask.total_steps}
                      </span>
                      <span>{selectedTask.progress}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-3">
                      <div
                        className="bg-blue-500 h-3 rounded-full transition-all duration-300"
                        style={{ width: `${selectedTask.progress}%` }}
                      />
                    </div>
                    {selectedTask.current_description && (
                      <p className="mt-2 text-sm text-gray-700">
                        <span className="font-medium">Current action:</span>{' '}
                        {selectedTask.current_description}
                      </p>
                    )}
                  </div>
                )}

                {/* Screenshot */}
                {selectedTask.screenshot_url && (
                  <div className="mb-6">
                    <h3 className="text-lg font-medium mb-3 flex items-center">
                      <EyeIcon className="h-5 w-5 mr-2" />
                      Latest Screenshot
                    </h3>
                    <img
                      src={selectedTask.screenshot_url}
                      alt="Screenshot"
                      className="w-full border rounded-lg"
                    />
                  </div>
                )}

                {/* Video & Trace Downloads */}
                {(selectedTask.video_url || selectedTask.trace_url) && (
                  <div className="mb-6 flex gap-4">
                    {selectedTask.video_url && (
                      <a
                        href={selectedTask.video_url}
                        download
                        className="flex items-center px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600"
                      >
                        <VideoCameraIcon className="h-5 w-5 mr-2" />
                        Download Video
                      </a>
                    )}
                    {selectedTask.trace_url && (
                      <a
                        href={selectedTask.trace_url}
                        download
                        className="flex items-center px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600"
                      >
                        <DocumentArrowDownIcon className="h-5 w-5 mr-2" />
                        Download Trace
                      </a>
                    )}
                  </div>
                )}

                {/* Error */}
                {selectedTask.error && (
                  <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <h3 className="text-lg font-medium text-red-800 mb-2">Error</h3>
                    <p className="text-sm text-red-700">{selectedTask.error}</p>
                  </div>
                )}

                {/* Event Log */}
                <div>
                  <h3 className="text-lg font-medium mb-3">Event Log</h3>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {selectedTask.events.map((event, index) => (
                      <div
                        key={index}
                        className="p-3 bg-gray-50 rounded-lg text-sm border border-gray-200"
                      >
                        <div className="flex justify-between items-start">
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium ${
                              event.type === 'completed'
                                ? 'bg-green-100 text-green-800'
                                : event.type === 'step_failed'
                                ? 'bg-red-100 text-red-800'
                                : event.type === 'recovery'
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-blue-100 text-blue-800'
                            }`}
                          >
                            {event.type}
                          </span>
                          <span className="text-xs text-gray-500">
                            {new Date(event.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        {event.description && (
                          <p className="mt-1 text-gray-700">{event.description}</p>
                        )}
                        {event.error && (
                          <p className="mt-1 text-red-600">{event.error}</p>
                        )}
                        {event.strategy && (
                          <p className="mt-1 text-gray-700">
                            Strategy: {event.strategy} - {event.reason}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-white shadow rounded-lg p-12 text-center text-gray-500">
                <EyeIcon className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                <p>Select a task to view details</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
