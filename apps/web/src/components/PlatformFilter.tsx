type PlatformFilterProps = {
  value: string;
  platforms: string[];
  disabled?: boolean;
  onChange: (platform: string) => void;
};

export function PlatformFilter({ value, platforms, disabled, onChange }: PlatformFilterProps) {
  return (
    <fieldset className="chip-field" disabled={disabled}>
      <legend className="field__label">Platform</legend>
      <div className="chip-group">
        <button
          type="button"
          className={value === "" ? "chip chip--platform chip--selected" : "chip chip--platform"}
          aria-pressed={value === ""}
          onClick={() => onChange("")}
        >
          All platforms
        </button>
        {platforms.map((code) => (
          <button
            type="button"
            key={code}
            className={value === code ? "chip chip--platform chip--selected" : "chip chip--platform"}
            aria-pressed={value === code}
            onClick={() => onChange(code)}
          >
            {code}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
