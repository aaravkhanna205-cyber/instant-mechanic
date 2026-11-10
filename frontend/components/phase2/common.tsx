"use client";
import Link from "next/link";
import React,{useState} from "react";
export function PageTitle({title,subtitle,action}:{title:string;subtitle:string;action?:React.ReactNode}){return <div className="flex flex-wrap items-start justify-between gap-4 mb-6"><div><h1 className="title">{title}</h1><p className="text-muted mt-1">{subtitle}</p></div>{action}</div>}
export function ActionLink({href,children}:{href:string;children:React.ReactNode}){return <Link className="btn btn-primary" href={href}>{children}</Link>}
export function DemoNotice(){return <div className="demo-note" role="note"><strong>Demo data · Phase 2</strong> — Changes are stored in this browser only. No real candidates are contacted and no files are uploaded to a server.</div>}
export function Empty({text}:{text:string}){return <div className="panel p-10 text-center text-muted">{text}</div>}
export function Pill({children}:{children:React.ReactNode}){return <span className="badge">{children}</span>}
export function Field({label,children}:{label:string;children:React.ReactNode}){return <label className="block space-y-1"><span className="text-xs text-muted font-semibold">{label}</span>{children}</label>}
export function DemoButton({children,onClick,primary=false,disabled=false}:{children:React.ReactNode;onClick:()=>void;primary?:boolean;disabled?:boolean}){return <button type="button" className={`btn ${primary?"btn-primary":""}`} onClick={onClick} disabled={disabled}>{children}</button>}
export function Feedback(){const [message,setMessage]=useState("");return {message,setMessage,notice:message?<div className="demo-note" role="status">{message} <button type="button" className="ml-3 underline" onClick={()=>setMessage("")}>Dismiss</button></div>:null}}
