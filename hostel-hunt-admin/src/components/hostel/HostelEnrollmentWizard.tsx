import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { StepProgress } from '../ui/StepProgress';
import { Step1BasicDetails } from './steps/Step1BasicDetails';
import { Step2HostelInfo } from './steps/Step2HostelInfo';
import { Step3Amenities } from './steps/Step3Amenities';
import { Step4MediaUpload } from './steps/Step4MediaUpload';
import { Step5RoomConfig } from './steps/Step5RoomConfig';
import { Step6Review } from './steps/Step6Review';
import { useAuth } from '../../contexts/AuthContext';
import { INITIAL_ENROLLMENT_STATE } from '../../types';
import type { HostelEnrollmentState } from '../../types';

const STEPS = [
  { label: 'Details' },
  { label: 'Info' },
  { label: 'Amenities' },
  { label: 'Media' },
  { label: 'Rooms' },
  { label: 'Review' },
];

interface Props {
  onClose?: () => void;
}

export const HostelEnrollmentWizard: React.FC<Props> = ({ onClose }) => {
  const { setEnrollmentComplete } = useAuth();
  const navigate = useNavigate();

  const [currentStep, setCurrentStep] = useState(0);
  const [data, setData] = useState<HostelEnrollmentState>(INITIAL_ENROLLMENT_STATE);
  const [errors, setErrors] = useState<Partial<Record<keyof HostelEnrollmentState, string>>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleChange = (key: keyof HostelEnrollmentState, value: unknown) => {
    setData(prev => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors(prev => ({ ...prev, [key]: undefined }));
  };

  // Validation per step
  const validateStep = (step: number): boolean => {
    const newErrors: Partial<Record<keyof HostelEnrollmentState, string>> = {};

    if (step === 0) {
      if (!data.name.trim()) newErrors.name = 'Hostel name is required';
      if (!data.owner_name.trim()) newErrors.owner_name = 'Owner name is required';
      if (!data.contact_number.trim()) newErrors.contact_number = 'Contact number is required';
      if (!data.email.trim()) newErrors.email = 'Email is required';
      if (!data.address.trim()) newErrors.address = 'Address is required';
      if (!data.city.trim()) newErrors.city = 'City is required';
      if (!data.state.trim()) newErrors.state = 'State is required';
      if (!data.pincode.trim()) newErrors.pincode = 'Pincode is required';
    }

    if (step === 1) {
      if (!data.gender_type) newErrors.gender_type = 'Please select hostel type';
      if (!data.total_floors) newErrors.total_floors = 'Required';
      if (!data.total_rooms) newErrors.total_rooms = 'Required';
      if (!data.total_beds) newErrors.total_beds = 'Required';
      if (!data.description.trim()) newErrors.description = 'Description is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(s => Math.min(s + 1, STEPS.length - 1));
    }
  };

  const handleBack = () => {
    setErrors({});
    setCurrentStep(s => Math.max(s - 1, 0));
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      // API: POST /hostels – data maps 1:1 to PostgreSQL hostels table
      await new Promise(r => setTimeout(r, 1500));
      setSubmitted(true);
      setTimeout(() => {
        setEnrollmentComplete();
        navigate('/dashboard');
      }, 2500);
    } catch {
      // handle error
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Success Screen ────────────────────────────────────────────────────────────
  if (submitted) {
    return (
      <div className="bg-[#141414] border border-[#2A2A2A] rounded-2xl w-full max-w-lg mx-auto p-12 text-center">
        <div className="w-24 h-24 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-12 h-12 text-green-400 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">Hostel Registered! 🎉</h2>
        <p className="text-[#9A9690] text-sm mb-2">
          <span className="text-white font-semibold">{data.name}</span> has been submitted for review.
        </p>
        <p className="text-[#4A4A4A] text-xs">Redirecting to your dashboard...</p>
        <div className="mt-6 h-1 bg-[#2A2A2A] rounded-full overflow-hidden">
          <div className="h-full bg-[#E8571A] animate-[progress_2.5s_ease-out_forwards]" style={{ width: '0%' }} />
        </div>
      </div>
    );
  }

  // ── Wizard ────────────────────────────────────────────────────────────────────
  return (
    <div className="bg-[#141414] border border-[#2A2A2A] rounded-2xl w-full max-w-3xl mx-auto flex flex-col max-h-[90vh] shadow-2xl">
      {/* Header */}
      <div className="px-8 pt-7 pb-6 border-b border-[#2A2A2A] flex-shrink-0">
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-xl font-bold text-white">Register Your Hostel</h2>
            <p className="text-[#9A9690] text-sm mt-0.5">
              Step {currentStep + 1} of {STEPS.length} · Complete all steps to list your property
            </p>
          </div>
          {onClose && (
            <button onClick={onClose}
              className="text-[#4A4A4A] hover:text-white transition-colors p-1 flex-shrink-0"
              title="Close">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
        <StepProgress steps={STEPS} currentStep={currentStep} />
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-8 py-6 min-h-0">
        {currentStep === 0 && <Step1BasicDetails data={data} onChange={handleChange} errors={errors} />}
        {currentStep === 1 && <Step2HostelInfo data={data} onChange={handleChange} errors={errors} />}
        {currentStep === 2 && <Step3Amenities data={data} onChange={handleChange} />}
        {currentStep === 3 && <Step4MediaUpload data={data} onChange={handleChange} />}
        {currentStep === 4 && <Step5RoomConfig data={data} onChange={handleChange} />}
        {currentStep === 5 && (
          <Step6Review
            data={data}
            onEditStep={setCurrentStep}
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting}
          />
        )}
      </div>

      {/* Footer nav */}
      {currentStep < 5 && (
        <div className="px-8 py-5 border-t border-[#2A2A2A] flex justify-between items-center flex-shrink-0">
          <button
            type="button"
            onClick={handleBack}
            disabled={currentStep === 0}
            className="flex items-center gap-2 px-5 py-2.5 border border-[#2A2A2A] hover:border-[#3A3A3A] text-[#9A9690] hover:text-white rounded-[10px] font-medium text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </button>

          <div className="text-[12px] text-[#4A4A4A] font-medium">
            {currentStep + 1} / {STEPS.length}
          </div>

          <button
            type="button"
            onClick={handleNext}
            className="flex items-center gap-2 bg-[#E8571A] hover:bg-[#FF6B35] text-white font-semibold px-6 py-2.5 rounded-[10px] transition-all orange-glow"
          >
            {currentStep === STEPS.length - 2 ? 'Review' : 'Next'}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
};
