import React from 'react';
import { DollarSign, Percent, Package, Clock } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface KPIGaugeProps {
  name: string;
  value: string;
  type: string;
}

export const KPIGauge: React.FC<KPIGaugeProps> = ({ name, value, type }) => {
  const getIcon = () => {
    switch (type) {
      case 'currency': return <DollarSign className="w-5 h-5" />;
      case 'percentage': return <Percent className="w-5 h-5" />;
      case 'stock': return <Package className="w-5 h-5" />;
      default: return <Clock className="w-5 h-5" />;
    }
  };

  const isPositive = !value.startsWith('-');

  return (
    <div className="glass-panel p-6 rounded-2xl flex flex-col gap-4 border border-outline-variant hover:border-primary-container transition-all group overflow-hidden relative">
      <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full -mr-12 -mt-12 transition-transform group-hover:scale-125" />
      
      <div className="flex items-start justify-between">
        <div className="p-2 rounded-xl bg-secondary-container/30 text-primary">
          {getIcon()}
        </div>
        <div className={cn(
          "px-2 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase",
          isPositive ? "bg-success-container/20 text-success" : "bg-error-container/20 text-error"
        )}>
          {isPositive ? 'Optimal' : 'Review'}
        </div>
      </div>

      <div>
        <p className="text-sm font-medium text-on-surface-variant mb-1 group-hover:text-primary transition-colors">
          {name}
        </p>
        <h3 className="text-2xl font-bold tracking-tight text-on-surface">
          {value}
        </h3>
      </div>
      
      <div className="h-1.5 w-full bg-surface-container-highest rounded-full overflow-hidden">
        <div 
          className="h-full bg-linear-to-r from-primary to-primary-container transition-all duration-1000" 
          style={{ width: isPositive ? '75%' : '35%' }} 
        />
      </div>
    </div>
  );
};
