import React from 'react';

interface Step {
  label: string;
  icon?: React.ReactNode;
}

interface StepProgressProps {
  steps: Step[];
  currentStep: number; // 0-indexed
  className?: string;
}

export const StepProgress: React.FC<StepProgressProps> = ({ steps, currentStep, className = '' }) => {
  return (
    <div className={`flex items-center w-full ${className}`}>
      {steps.map((step, i) => {
        const isComplete = i < currentStep;
        const isActive = i === currentStep;

        return (
          <React.Fragment key={i}>
            <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
              {/* Circle */}
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${
                  isComplete
                    ? 'bg-[#E8571A] text-white shadow-[0_0_12px_rgba(232,87,26,0.4)]'
                    : isActive
                    ? 'bg-[#E8571A]/20 border-2 border-[#E8571A] text-[#E8571A]'
                    : 'bg-[#1A1A1A] border-2 border-[#2A2A2A] text-[#4A4A4A]'
                }`}
              >
                {isComplete ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <span>{i + 1}</span>
                )}
              </div>
              {/* Label */}
              <span
                className={`text-[10px] font-semibold tracking-wide uppercase whitespace-nowrap transition-colors duration-300 ${
                  isComplete || isActive ? 'text-[#E8571A]' : 'text-[#4A4A4A]'
                }`}
              >
                {step.label}
              </span>
            </div>

            {/* Connector line */}
            {i < steps.length - 1 && (
              <div className="flex-1 h-[2px] mx-2 rounded-full relative overflow-hidden bg-[#2A2A2A]">
                <div
                  className="absolute inset-y-0 left-0 bg-[#E8571A] transition-all duration-500 ease-out rounded-full"
                  style={{ width: isComplete ? '100%' : '0%' }}
                />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};
