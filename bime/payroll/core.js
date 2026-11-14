/* Payroll calculation and import/export contract. No company data is bundled. */
(function(root){
"use strict";
const HEAD=["ID","Commission","Commission2","Penalty","ActiveDayD","ActiveDayH","ActiveDayM","FunctionD","FunctionH","FunctionM","AbsenceD","AbsenceH","AbsenceM","OvertimeH","OvertimeM","OvertimeHolidayH","OvertimeHolidayM","ShiftWorkH","ShiftWorkM","NightWorkH","NightWorkM","VacationPaidD","VacationPaidH","VacationPaidM","VacationSickD","VacationSickH","VacationSickM","AssignmentN","AssignmentH"];
const FIELDS={work:"کارکرد روز",absD:"غیبت روز",absH:"غیبت ساعت",absM:"غیبت دقیقه",fixed:"مازاد ثابت (ریال)",variable:"مازاد متغیر (ریال)",commission:"پورسانت واقعی (ریال)",reserve:"ذخیره پورسانت (ریال)",penalty:"جریمه (ریال)",factor:"ضریب مأموریت دستی (اختیاری)",holH:"تعطیل‌کاری ساعت",holM:"تعطیل‌کاری دقیقه",shiftH:"نوبت‌کاری ساعت",shiftM:"نوبت‌کاری دقیقه",nightH:"شب‌کاری ساعت",nightM:"شب‌کاری دقیقه",vacD:"مرخصی استحقاقی روز",vacH:"مرخصی استحقاقی ساعت",vacM:"مرخصی استحقاقی دقیقه",sickD:"مرخصی استعلاجی روز",sickH:"مرخصی استعلاجی ساعت",sickM:"مرخصی استعلاجی دقیقه",actualMission:"روز مأموریت مستند",actualH:"ساعت اضافه‌کاری مستند",actualM:"دقیقه اضافه‌کاری مستند"};
const num=v=>{let s=String(v??"").trim().replace(/[۰-۹]/g,c=>String(c.charCodeAt(0)-1776)).replace(/[٠-٩]/g,c=>String(c.charCodeAt(0)-1632)).replace(/[,\u066c\s]/g,"").replace(/\u066b/g,"."); if(!s)return 0;if(!/^\d+(\.\d+)?$/.test(s))throw Error("عدد نامعتبر: "+s);let n=Number(s);if(!Number.isFinite(n)||n>1e12)throw Error("عدد خارج از محدوده");return n};
const norm=s=>String(s??"").replace(/ي/g,"ی").replace(/ك/g,"ک").replace(/[\s\u200c]/g,"");
const empty=()=>Object.fromEntries(Object.keys(FIELDS).map(k=>[k,0]));
const monthKey=(y,m)=>String(y)+"-"+String(m).padStart(2,"0");
const nextMonth=k=>{const [y,m]=k.split("-").map(Number);return monthKey(y+(m===12?1:0),m===12?1:m+1)};
const monthDays=k=>{const [y,m]=k.split("-").map(Number);return m<=6?31:m<=11?30:(new Intl.DateTimeFormat("en-u-ca-persian",{year:"numeric",month:"numeric",day:"numeric"}).formatToParts(new Date(Date.UTC(y+621,2,20))).find(p=>p.type==="year")?.value===String(y)?30:29)};
function compute(p,r){
 const v=k=>num(r[k]), base=num(p.wage)+num(p.seniority), sales=norm(p.job).includes("بازاریاب"), factor=v("factor")|| (sales?2:1), rate=base*factor, net=Math.max(0,v("commission")-v("reserve")), pool=v("fixed")+v("variable"), minuteRate=Math.round(base*1.4/440);
 const fromCommission=sales&&rate?Math.min(25,Math.floor(net/rate)):0;
 const fromSurplus=rate?Math.min(25-fromCommission,Math.floor(pool/rate)):0;
 const plannedDays=fromCommission+fromSurplus, plannedCommission=net-fromCommission*rate;
 const plannedRest=pool-fromSurplus*rate, plannedMinutes=minuteRate?Math.floor(plannedRest/minuteRate):0;
 // Only documented work is reported. Allocation is capped at documented days/minutes and the available budget.
 const actualDays=v("actualMission"), actualMinutes=v("actualH")*60+v("actualM");
 const paidDays=Math.min(actualDays,plannedDays), paidFromCommission=Math.min(paidDays,fromCommission), paidFromSurplus=paidDays-paidFromCommission;
 const commission=net-paidFromCommission*rate, rest=pool-paidFromSurplus*rate;
 const allocatedMinutes=minuteRate?Math.min(actualMinutes,Math.floor(rest/minuteRate)):0;
 const unallocated=rest-allocatedMinutes*minuteRate;
 const errors=[], warnings=[];
 if(!base||!p.job||!num(p.wage))errors.push("حکم ناقص");
 if(v("reserve")>v("commission"))errors.push("ذخیره بیشتر از پورسانت");
 if(!Number.isInteger(actualDays)||actualDays>25)errors.push("روز مأموریت مستند خارج از ۰ تا ۲۵");
 if(!Number.isInteger(v("actualH"))||!Number.isInteger(v("actualM"))||v("actualM")>59)errors.push("زمان اضافه‌کاری مستند نامعتبر");
 if(factor>5)errors.push("ضریب مأموریت نامعتبر");
 for(const k of Object.keys(FIELDS))if(k!=="factor"&&!Number.isInteger(v(k)))errors.push(FIELDS[k]+" باید عدد صحیح باشد");
 for(const k of ["absM","vacM","sickM","holM","shiftM","nightM"])if(v(k)>59)errors.push(FIELDS[k]+" باید ۰ تا ۵۹ باشد");
 if(v("work")>31||v("absD")>31||v("vacD")>31||v("sickD")>31)errors.push("تعداد روز نامعتبر");
 if(actualDays>plannedDays||actualMinutes>plannedMinutes)warnings.push("کارکرد مستند بیش از بودجه پیشنهادی؛ مبلغ اضافه جداگانه کنترل شود");
 if(unallocated>0)warnings.push("مانده مازاد: "+Math.round(unallocated).toLocaleString("fa-IR")+" ریال؛ جداگانه پرداخت و کنترل شود");
 if(plannedDays>actualDays||plannedMinutes>actualMinutes)warnings.push("پیشنهاد بودجه با کارکرد مستند برابر نیست");
 return {base,sales,factor,rate,net,pool,minuteRate,fromCommission,fromSurplus,plannedDays,plannedCommission,plannedMinutes,plannedRemainder:plannedRest-plannedMinutes*minuteRate,actualDays,actualMinutes,commission,unallocated,errors,warnings};
}
function exportRow(p,r,c){const v=k=>num(r[k]);if(c.errors.length)throw Error(c.errors.join("؛ "));return [num(p.id),Math.round(c.commission),0,v("penalty"),0,0,0,v("work"),0,0,v("absD"),v("absH"),v("absM"),v("actualH"),v("actualM"),v("holH"),v("holM"),v("shiftH"),v("shiftM"),v("nightH"),v("nightM"),v("vacD"),v("vacH"),v("vacM"),v("sickD"),v("sickH"),v("sickM"),v("actualMission"),0]}
function importBook(book){
 const master=book.find(s=>s.name==="اطلاعات پرسنل"), input=book.find(s=>s.name==="ورود عملکرد");
 if(!master||!input)throw Error("فایل پنج‌شیتی مدیریت احکام و عملکرد را انتخاب کنید.");
 const map=new Map(),rows={};
 for(const a of master.rows){if(a["شناسه کارآمد"]===""||a["شناسه کارآمد"]==null)continue;const id=num(a["شناسه کارآمد"]);if(!id||!Number.isInteger(id)||map.has(id))throw Error("شناسه نامعتبر یا تکراری");const p={id,code:String(a["کد پرسنلی"]??""),name:String(a["نام کامل"]??""),job:String(a["عنوان شغل بیمه"]??""),jobCode:String(a["کد شغل بیمه"]??""),wage:num(a["مزد روزانه (ریال)"]),seniority:num(a["پایه سنوات تجمیعی روزانه (ریال)"]),group:String(a["گروه بیمه در فایل مبدا"]??""),hire:String(a["تاریخ استخدام"]??""),senStart:String(a["تاریخ شروع پایه سنوات"]??""),children:num(a["تعداد فرزندان"]),marital:String(a["وضعیت تأهل"]??""),active:true};if(!p.name||!p.code)throw Error("اطلاعات هویتی ناقص");map.set(id,p);rows[id]=empty()}
 const seen=new Set();for(const a of input.rows){if(a["شناسه کارآمد"]===""||a["شناسه کارآمد"]==null)continue;const id=num(a["شناسه کارآمد"]);if(!map.has(id)||seen.has(id))throw Error("شناسه عملکرد نامعتبر یا تکراری: "+id);seen.add(id);for(const [k,label] of Object.entries(FIELDS))if(!k.startsWith("actual"))rows[id][k]=num(a[label]);}
 if(seen.size!==map.size||!map.size)throw Error("شناسه‌های دو شیت برابر نیستند");
 return {people:[...map.values()].sort((a,b)=>Number(a.code)-Number(b.code)),rows};
}
function copyMonth(source,people,fields){const allowed=new Set(Object.keys(FIELDS).filter(k=>!k.startsWith("actual")));return Object.fromEntries(people.filter(p=>p.active!==false).map(p=>[p.id,{...empty(),...Object.fromEntries(fields.filter(k=>allowed.has(k)).map(k=>[k,num(source[p.id]?.[k])]))}]))}
const api={HEAD,FIELDS,num,norm,empty,monthKey,nextMonth,compute,exportRow,importBook,copyMonth};if(typeof module!=="undefined")module.exports=api;else root.Payroll=api;
})(typeof globalThis!=="undefined"?globalThis:this);
