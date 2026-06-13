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
  const handleChange = (rawValue: string) => {
    if (rawValue.trim() === "") {
      return;
    }
    const nextValue = Number(rawValue);
    if (Number.isFinite(nextValue)) {
      onValue(nextValue);
    }
  };

  return (
    <label>
      {label}
      <input
        inputMode="decimal"
        max={max}
        min={min}
        onChange={(event) => handleChange(event.target.value)}
        onWheel={(event) => event.currentTarget.blur()}
        step={step}
        type="number"
        value={value}
      />
    </label>
  );
}
