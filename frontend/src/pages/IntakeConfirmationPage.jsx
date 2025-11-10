import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';

const IntakeConfirmationPage = () => {
  const { intakeId } = useParams();
  const navigate = useNavigate();

  const { data: intake, isLoading, error } = useQuery({
    queryKey: ['intake', intakeId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/api/scheduling/intake/patient/${intakeId}`);
      if (!response.ok) {
        throw new Error('Failed to load intake information');
      }
      return response.json();
    },
    enabled: !!intakeId,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading intake information...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md">
          <div className="text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 mb-4">
              <svg
                className="h-6 w-6 text-red-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Error</h2>
            <p className="text-gray-600 mb-4">{error.message}</p>
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition"
            >
              Go to Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'in_review':
        return 'bg-blue-100 text-blue-800';
      case 'approved':
        return 'bg-green-100 text-green-800';
      case 'rejected':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getInsuranceStatusColor = (status) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'verified':
        return 'bg-green-100 text-green-800';
      case 'expired':
      case 'invalid':
        return 'bg-red-100 text-red-800';
      case 'auth_required':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        {/* Success Banner */}
        <div className="bg-white rounded-lg shadow-lg p-8 mb-6">
          <div className="text-center">
            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100 mb-4">
              <svg
                className="h-10 w-10 text-green-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Intake Form Submitted!</h1>
            <p className="text-lg text-gray-600 mb-4">
              Thank you, {intake?.first_name} {intake?.last_name}. We have received your intake
              form.
            </p>
            <div className="inline-block bg-blue-50 rounded-lg px-6 py-3">
              <p className="text-sm text-gray-600">Your Intake ID</p>
              <p className="text-2xl font-mono font-bold text-blue-600">#{intake?.id}</p>
            </div>
          </div>
        </div>

        {/* Status Information */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Status Information</h2>

          <div className="space-y-4">
            <div className="flex justify-between items-center py-3 border-b">
              <div>
                <p className="text-sm font-medium text-gray-700">Intake Status</p>
                <p className="text-xs text-gray-500 mt-1">Current processing stage</p>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-sm font-medium capitalize ${getStatusColor(
                  intake?.intake_status
                )}`}
              >
                {intake?.intake_status?.replace('_', ' ')}
              </span>
            </div>

            <div className="flex justify-between items-center py-3 border-b">
              <div>
                <p className="text-sm font-medium text-gray-700">Insurance Verification</p>
                <p className="text-xs text-gray-500 mt-1">Eligibility check status</p>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-sm font-medium capitalize ${getInsuranceStatusColor(
                  intake?.insurance_status
                )}`}
              >
                {intake?.insurance_status?.replace('_', ' ')}
              </span>
            </div>

            <div className="flex justify-between items-center py-3">
              <div>
                <p className="text-sm font-medium text-gray-700">Submitted At</p>
                <p className="text-xs text-gray-500 mt-1">Date and time received</p>
              </div>
              <span className="text-sm text-gray-600">
                {intake?.submitted_at
                  ? new Date(intake.submitted_at).toLocaleString('en-US', {
                      dateStyle: 'medium',
                      timeStyle: 'short',
                    })
                  : 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* What Happens Next */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">What Happens Next?</h2>

          <div className="space-y-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <div className="flex items-center justify-center h-8 w-8 rounded-full bg-blue-100 text-blue-600 font-semibold">
                  1
                </div>
              </div>
              <div className="ml-4">
                <h3 className="text-sm font-medium text-gray-900">Insurance Verification</h3>
                <p className="mt-1 text-sm text-gray-600">
                  We will verify your insurance eligibility and coverage. This typically takes 1-2
                  business days.
                </p>
              </div>
            </div>

            <div className="flex">
              <div className="flex-shrink-0">
                <div className="flex items-center justify-center h-8 w-8 rounded-full bg-blue-100 text-blue-600 font-semibold">
                  2
                </div>
              </div>
              <div className="ml-4">
                <h3 className="text-sm font-medium text-gray-900">Intake Review</h3>
                <p className="mt-1 text-sm text-gray-600">
                  Our team will review your intake form and medical information to ensure we can
                  provide the best care.
                </p>
              </div>
            </div>

            <div className="flex">
              <div className="flex-shrink-0">
                <div className="flex items-center justify-center h-8 w-8 rounded-full bg-blue-100 text-blue-600 font-semibold">
                  3
                </div>
              </div>
              <div className="ml-4">
                <h3 className="text-sm font-medium text-gray-900">Therapist Assignment</h3>
                <p className="mt-1 text-sm text-gray-600">
                  We'll match you with a therapist who specializes in your condition and fits your
                  scheduling preferences.
                </p>
              </div>
            </div>

            <div className="flex">
              <div className="flex-shrink-0">
                <div className="flex items-center justify-center h-8 w-8 rounded-full bg-blue-100 text-blue-600 font-semibold">
                  4
                </div>
              </div>
              <div className="ml-4">
                <h3 className="text-sm font-medium text-gray-900">Appointment Scheduling</h3>
                <p className="mt-1 text-sm text-gray-600">
                  You'll receive a call or email to schedule your first appointment at your
                  preferred time.
                </p>
              </div>
            </div>

            <div className="flex">
              <div className="flex-shrink-0">
                <div className="flex items-center justify-center h-8 w-8 rounded-full bg-green-100 text-green-600 font-semibold">
                  5
                </div>
              </div>
              <div className="ml-4">
                <h3 className="text-sm font-medium text-gray-900">First Visit</h3>
                <p className="mt-1 text-sm text-gray-600">
                  Attend your first appointment and begin your personalized therapy program!
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Contact Information */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold text-blue-900 mb-3">Need Help?</h2>
          <div className="space-y-2 text-sm text-blue-800">
            <p>
              <strong>Phone:</strong> (555) 123-4567
            </p>
            <p>
              <strong>Email:</strong> intake@yourtherapyclinic.com
            </p>
            <p>
              <strong>Hours:</strong> Monday - Friday, 8:00 AM - 6:00 PM
            </p>
          </div>
          <p className="mt-4 text-sm text-blue-700">
            Please reference your Intake ID <strong>#{intake?.id}</strong> when contacting us.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-center space-x-4">
          <button
            onClick={() => window.print()}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition"
          >
            Print This Page
          </button>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition"
          >
            Return to Home
          </button>
        </div>
      </div>
    </div>
  );
};

export default IntakeConfirmationPage;
