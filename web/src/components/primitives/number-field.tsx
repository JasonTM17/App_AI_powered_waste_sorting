"use client";

type NumberFieldProps = {
  label: string;
  max?: number;
  min?: number;
  step?: number;
  value: number;
  onValue: (value: number) => void;
};

export function NumberField({
  label,
  max,
  min,
  step,
  value,
  onValue
}: NumberFieldProps) {
  return (
    <label>
      {label}
      <input
        max={max}
        min={min}
        step={step}
        type="number"
        value={value}
        onChange={(event) => onValue(Number(event.target.value))}
      />
    </label>
  );
}
