"use client";
import Link from "next/link";
import {useState} from "react";
import {Card,StatusBadge,Button} from "@/components/ui";
import {ArrowLeft,CheckCircle2} from "lucide-react";
export function PreviewPage({title,phase}:{title:string,phase:number}){const [message,setMessage]=useState(false);return <div className="space-y-5"><Link href="/dashboard" className="text-sm text-[var(--deep-orange)] inline-flex items-center gap-2"><ArrowLeft size={16}/> Dashboard</Link><div className="flex gap-3 items-center"><h1 className="title">{title}</h1><StatusBadge>Preview</StatusBadge></div><Card className="p-8 max-w-2xl"><CheckCircle2 color="#C2410C" size={28}/><h2 className="section-title mt-4">Foundation ready</h2><p className="text-muted mt-2 mb-5">The navigation and page shell are functional. The {title.toLowerCase()} workflow is scheduled for Phase {phase}. No live data or backend actions are available yet.</p><Button onClick={()=>setMessage(true)}>Show preview status</Button>{message&&<p role="status" className="mt-3 text-muted">This module is planned for Phase {phase}; nothing has been submitted.</p>}</Card></div>}
