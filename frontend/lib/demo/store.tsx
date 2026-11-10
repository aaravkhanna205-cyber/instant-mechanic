"use client";
import React,{createContext,useCallback,useContext,useEffect,useMemo,useState} from "react";
export type Stage="Applied"|"Screening"|"Trade test"|"Interview"|"Offer"|"Joined";
export type JobStatus="Draft"|"Published"|"Closed";
export type Job={id:string;title:string;location:string;department:string;type:string;description:string;skills:string[];status:JobStatus;created:string};
export type Candidate={id:string;name:string;email:string;phone:string;skills:string[];experience:string;education:string;resumeName:string;notes:string};
export type Application={id:string;jobId:string;candidateId:string;stage:Stage;date:string};
export type Interview={id:string;applicationId:string;date:string;mode:string;status:"Scheduled"|"Completed"|"Cancelled";notes:string};
export type Audit={id:string;action:string;by:string;date:string};
export type DemoState={jobs:Job[];candidates:Candidate[];applications:Application[];interviews:Interview[];audit:Audit[];settings:{company:string;stages:Stage[];applicationsOpen:boolean}};
const stages:Stage[]=["Applied","Screening","Trade test","Interview","Offer","Joined"];
const initial:DemoState={jobs:[
{id:"job-101",title:"Automotive Technician",location:"Varanasi",department:"Workshop",type:"Full-time",description:"Inspect vehicles, diagnose mechanical faults, document repairs and maintain workshop safety.",skills:["Engine repair","Brakes","OBD diagnostics"],status:"Published",created:"2026-11-05"},
{id:"job-102",title:"Service Advisor",location:"Varanasi",department:"Customer Operations",type:"Full-time",description:"Coordinate service bookings and communicate estimates and work status clearly.",skills:["Customer service","Service estimates","CRM"],status:"Published",created:"2026-11-06"},
{id:"job-103",title:"Auto Electrician",location:"Delhi",department:"Workshop",type:"Full-time",description:"Troubleshoot wiring, sensors and electrical systems using diagnostic tools.",skills:["Electrical diagnostics","Wiring","Multimeter"],status:"Draft",created:"2026-11-08"},
{id:"job-104",title:"Operations Executive",location:"Remote",department:"Operations",type:"Contract",description:"Track operational cases and coordinate customer and mechanic communications.",skills:["Excel","CRM","Communication"],status:"Published",created:"2026-11-09"}],
candidates:[{id:"can-101",name:"Rohan Sharma",email:"rohan@example.com",phone:"9990001001",skills:["Engine repair","Brakes","OBD diagnostics"],experience:"3 years automotive workshop",education:"ITI Automobile",resumeName:"rohan-resume.pdf",notes:""},
{id:"can-102",name:"Priya Verma",email:"priya@example.com",phone:"9990001002",skills:["CRM","Customer service"],experience:"2 years service centre",education:"B.Com",resumeName:"priya-cv.docx",notes:""},
{id:"can-103",name:"Amit Singh",email:"amit@example.com",phone:"9990001003",skills:["Electrical diagnostics","Multimeter"],experience:"4 years auto electrical",education:"ITI Electrician",resumeName:"amit-resume.pdf",notes:""}],
applications:[{id:"app-101",jobId:"job-101",candidateId:"can-101",stage:"Trade test",date:"2026-11-07"},{id:"app-102",jobId:"job-102",candidateId:"can-102",stage:"Interview",date:"2026-11-08"},{id:"app-103",jobId:"job-103",candidateId:"can-103",stage:"Applied",date:"2026-11-09"}],
interviews:[{id:"int-101",applicationId:"app-102",date:"2026-11-15T11:00",mode:"Video",status:"Scheduled",notes:"Discuss service-case escalation"}],audit:[],settings:{company:"Instant Mechanic",stages,applicationsOpen:true}};
const STORAGE="instant-mechanic-hire-phase2-demo-v1";
const id=(prefix:string)=>`${prefix}-${Date.now()}-${Math.random().toString(36).slice(2,7)}`;
function safeParse(json:string|null):DemoState {if(!json)return initial;try {const raw=JSON.parse(json) as DemoState;if(!Array.isArray(raw.jobs)||!Array.isArray(raw.candidates)||!Array.isArray(raw.applications))return initial;return {...initial,...raw,settings:{...initial.settings,...raw.settings}}}catch{return initial}}
type DemoContextValue={data:DemoState;hydrated:boolean;update:(fn:(s:DemoState)=>DemoState,action:string)=>void;reset:()=>void;newId:(p:string)=>string};
const Context=createContext<DemoContextValue|null>(null);
export function DemoProvider({children}:{children:React.ReactNode}){const [data,setData]=useState<DemoState>(initial);const [hydrated,setHydrated]=useState(false);
useEffect(()=>{const saved=safeParse(window.localStorage.getItem(STORAGE));queueMicrotask(()=>{setData(saved);setHydrated(true)})},[]);
const update=useCallback((fn:(s:DemoState)=>DemoState,action:string)=>{setData(old=>{const next=fn(old);const state={...next,audit:[{id:id("log"),action,by:"Demo HR user",date:new Date().toISOString()},...next.audit].slice(0,150)};localStorage.setItem(STORAGE,JSON.stringify(state));return state})},[]);
const reset=useCallback(()=>{localStorage.removeItem(STORAGE);setData(initial)},[]);
const value=useMemo(()=>({data,hydrated,update,reset,newId:id}),[data,hydrated,update,reset]);return <Context.Provider value={value}>{children}</Context.Provider>}
export function useDemo(){const ctx=useContext(Context);if(!ctx)throw new Error("useDemo must be within DemoProvider");return ctx}
export const HIRING_STAGES=stages;
