'use client';

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

export default function StepProgress({ steps, currentStep, className = '' }: StepProgressProps) {
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
                    ? 'bg-auburn-500 text-ivory-50 shadow-md shadow-auburn-500/40 dark:bg-auburn-300 dark:text-ink-900 dark:shadow-auburn-300/40'
                    : isActive
                      ? 'bg-auburn-500/20 border-2 border-auburn-500 text-auburn-500 dark:bg-auburn-300/20 dark:border-auburn-300 dark:text-auburn-300'
                      : 'bg-ivory-100 border-2 border-ivory-300 text-ink-700 dark:bg-ivory-900 dark:border-ivory-700 dark:text-ivory-500'
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
                  isComplete || isActive ? 'text-auburn-500 dark:text-auburn-300' : 'text-ink-700 dark:text-ivory-500'
                }`}
              >
                {step.label}
              </span>
            </div>

            {/* Connector line */}
            {i < steps.length - 1 && (
              <div className="flex-1 h-[2px] mx-2 rounded-full relative overflow-hidden bg-ivory-300 dark:bg-ivory-700">
                <div
                  className="absolute inset-y-0 left-0 bg-auburn-500 dark:bg-auburn-300 transition-all duration-500 ease-out rounded-full"
                  style={{ width: isComplete ? '100%' : '0%' }}
                />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
