import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useMutation } from '@tanstack/react-query';
import { FileText, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { api } from '../api/client';

export default function SubmitPage() {
  const navigate = useNavigate();
  const [submitResult, setSubmitResult] = useState(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm({
    defaultValues: {
      visit_type: 'PT',
      source: 'web_portal',
    },
  });

  const mutation = useMutation({
    mutationFn: (data) => api.submitNote(data),
    onSuccess: (data) => {
      setSubmitResult(data);
      reset();
    },
    onError: (error) => {
      console.error('Submission error:', error);
    },
  });

  const onSubmit = (data) => {
    // Format visit_date to ISO string
    const visitDate = new Date(data.visit_date);
    const formattedData = {
      ...data,
      visit_date: visitDate.toISOString(),
    };
    mutation.mutate(formattedData);
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
          <FileText className="w-8 h-8 text-primary-600" />
          Submit Clinical Note
        </h1>
        <p className="text-gray-600 mt-2">
          Enter patient visit information and raw clinical notes. Our AI will structure it into SOAP format.
        </p>
      </div>

      {/* Success Message */}
      {submitResult && (
        <div className="card bg-green-50 border border-green-200 mb-6">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-6 h-6 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-green-900">Note Submitted Successfully!</h3>
              <p className="text-green-700 mt-1">{submitResult.message}</p>
              <div className="mt-3 flex gap-3">
                <button
                  onClick={() => navigate(`/tasks/${submitResult.task_id}`)}
                  className="btn btn-primary text-sm"
                >
                  View SOAP Note
                </button>
                <button
                  onClick={() => setSubmitResult(null)}
                  className="btn btn-secondary text-sm"
                >
                  Submit Another
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {mutation.isError && (
        <div className="card bg-red-50 border border-red-200 mb-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-red-900">Submission Failed</h3>
              <p className="text-red-700 mt-1">
                {mutation.error?.response?.data?.detail || 'An error occurred. Please try again.'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="card space-y-6">
        {/* Patient Information */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Patient Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">
                Patient ID <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                {...register('patient_id', { required: 'Patient ID is required' })}
                className="input"
                placeholder="PT-12345"
              />
              {errors.patient_id && (
                <p className="text-red-500 text-sm mt-1">{errors.patient_id.message}</p>
              )}
            </div>

            <div>
              <label className="label">First Name</label>
              <input
                type="text"
                {...register('patient_first_name')}
                className="input"
                placeholder="John"
              />
            </div>

            <div>
              <label className="label">Last Name</label>
              <input
                type="text"
                {...register('patient_last_name')}
                className="input"
                placeholder="Doe"
              />
            </div>

            <div>
              <label className="label">Date of Birth</label>
              <input
                type="date"
                {...register('patient_dob')}
                className="input"
              />
            </div>
          </div>
        </div>

        {/* Visit Information */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Visit Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">
                Visit Date & Time <span className="text-red-500">*</span>
              </label>
              <input
                type="datetime-local"
                {...register('visit_date', { required: 'Visit date is required' })}
                className="input"
              />
              {errors.visit_date && (
                <p className="text-red-500 text-sm mt-1">{errors.visit_date.message}</p>
              )}
            </div>

            <div>
              <label className="label">
                Visit Type <span className="text-red-500">*</span>
              </label>
              <select
                {...register('visit_type', { required: 'Visit type is required' })}
                className="input"
              >
                <option value="PT">Physical Therapy (PT)</option>
                <option value="OT">Occupational Therapy (OT)</option>
                <option value="SLP">Speech-Language Pathology (SLP)</option>
                <option value="Nursing">Nursing</option>
                <option value="Home Health">Home Health</option>
                <option value="SNF">Skilled Nursing Facility (SNF)</option>
              </select>
            </div>

            <div className="md:col-span-2">
              <label className="label">
                Submitted By <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                {...register('submitted_by', { required: 'Your name is required' })}
                className="input"
                placeholder="Jane Smith, PTA"
              />
              {errors.submitted_by && (
                <p className="text-red-500 text-sm mt-1">{errors.submitted_by.message}</p>
              )}
            </div>
          </div>
        </div>

        {/* Clinical Notes */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Clinical Notes</h2>
          <div>
            <label className="label">
              Raw Clinical Note <span className="text-red-500">*</span>
            </label>
            <textarea
              {...register('raw_input', {
                required: 'Clinical note is required',
                minLength: {
                  value: 20,
                  message: 'Note must be at least 20 characters',
                },
              })}
              className="input h-48 resize-y"
              placeholder="Example: Patient walked 100 feet with contact guard assist. Reports mild knee pain rated 3/10. Gait steady with good balance. Continue strengthening exercises and progress to supervision level next visit."
            />
            {errors.raw_input && (
              <p className="text-red-500 text-sm mt-1">{errors.raw_input.message}</p>
            )}
            <p className="text-gray-500 text-sm mt-1">
              Include patient complaints, observations, measurements, and treatment plan.
            </p>
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button
            type="button"
            onClick={() => reset()}
            className="btn btn-secondary"
            disabled={mutation.isPending}
          >
            Clear Form
          </button>
          <button
            type="submit"
            className="btn btn-primary flex items-center gap-2"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <FileText className="w-4 h-4" />
                Submit Note
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
