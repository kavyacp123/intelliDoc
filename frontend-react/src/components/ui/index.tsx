import React from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({ 
  className, 
  variant = 'primary', 
  isLoading, 
  children, 
  ...props 
}) => {
  const baseStyles = "flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all duration-150 active:scale-[0.98]";
  
  const variants = {
    primary: "primary-gradient text-on-primary shadow-atmospheric hover:opacity-90",
    secondary: "bg-surface-container-high text-on-surface hover:bg-surface-container-highest",
    ghost: "bg-transparent text-secondary hover:underline px-2 py-1"
  };

  return (
    <button 
      className={cn(baseStyles, variants[variant], className)} 
      disabled={isLoading || props.disabled}
      {...props}
    >
      {isLoading ? (
        <span className="animate-spin material-symbols-outlined text-[20px]">progress_activity</span>
      ) : children}
    </button>
  );
};

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export const Input: React.FC<InputProps> = ({ label, className, ...props }) => {
  return (
    <div className="space-y-2">
      {label && (
        <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant px-1">
          {label}
        </label>
      )}
      <input
        className={cn(
          "w-full px-4 py-3 bg-surface-container-low border-none rounded-lg focus:ring-2 focus:ring-secondary/20 transition-all text-sm tabular-nums placeholder:text-outline",
          className
        )}
        {...props}
      />
    </div>
  );
};
