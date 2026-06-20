"use client";
import { Eye, EyeOff } from "lucide-react";
import { useState, type InputHTMLAttributes } from "react";
export function PasswordInput(props: InputHTMLAttributes<HTMLInputElement> & { ariaLabel: string }) {
  const [visible, setVisible] = useState(false); const { ariaLabel, ...inputProps } = props;
  return <div className="password-input-control"><input {...inputProps} type={visible ? "text" : "password"}/><button aria-label={`${visible ? "Ẩn" : "Hiện"} ${ariaLabel}`} onClick={()=>setVisible(v=>!v)} type="button">{visible?<EyeOff size={17}/>:<Eye size={17}/>}</button></div>;
}
