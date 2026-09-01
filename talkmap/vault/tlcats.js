/* Vault Talk Map categories — drop-in replacement for the inline script in
 * recordings.organizedai.vip/vault. Generated to match lib/talkmap.py; the two
 * must change together or the pipeline's widgets and the site's map disagree.
 *
 * THREE EDITS, all inside the existing <script> block:
 *
 *   1. Replace the whole `const TLCATS=[...]` array with the one below.
 *   2. Add `tlCat()` immediately after it.
 *   3. In `loadTL`, replace these three lines:
 *
 *          const cat=TLCATS.slice(0,-1).find(k=>k.kw.test(t))
 *                 || TLCATS.slice(0,-1).find(k=>k.kw.test(s))
 *                 || TLCATS[TLCATS.length-1];
 *
 *      with:
 *
 *          const cat=tlCat(t,s);
 *
 * Optionally also extend `tlfix` with the two ASR names found in the real
 * chapters (see the bottom of this file).
 *
 * Nothing else changes: the ids `intro/qa/data/demo/tools/concept` keep their
 * meaning and colours, `build` is new, and every renderer already reads
 * `c.cat.color` / `c.cat.id` so SPINE, ORBIT, the legend and the fan pick the
 * new category up with no further work.
 */

const TLCATS=[
 {id:"intro",label:"Intro / Wrap",color:"#9a927f",kw:/\bintro\b|\bintroduc(?:tion|ing)\b|welcome|journey|opening|closing|wrap[- ]?up|outro|recap|appreciation|thank/i},
 {id:"qa",label:"Q&A",color:"#b48ead",kw:/q\s*&\s*a|\bquestions?\b|audience|discussion/i},
 {id:"data",label:"Data / Tokens",color:"#e0985a",kw:/\btokens?\b|\bcosts?\b|pricing|benchmark|\bresults?\b|\bmetrics?\b|\bstat(?:s|istics)?\b|performance/i},
 {id:"demo",label:"Live Demo",color:"#f5d623",kw:/\bdemos?\b|\bdemonstrat\w*|\blive\b|walk-?through|hands-on|\bcoding\b|\bscreen\b/i},
 {id:"build",label:"Build / Workflow",color:"#59a5a0",kw:/\bworkflows?\b|\bworkers?\b|\bskills?\b|\bbuild(?:ing)?\b|automat\w*|\barchitectures?\b|\bpipelines?\b|orchestrat\w*/i},
 {id:"tools",label:"Tools / Platform",color:"#90b97e",kw:/\bplatforms?\b|\bmcp\b|\bsetup\b|install\w*|integrat\w*|\bapis?\b|\bsdk\b|\bstack\b|\btool(?:s|box|ing)?\b|config\w*|deploy\w*/i},
 {id:"concept",label:"Concepts",color:"#7aa2c9",kw:/./}
];

/* Scored, not first-match. A chapter title is a deliberate label and outranks
   any summary; among summaries, more distinct hits win. Ties go to the earlier
   category. Previously an earlier category's passing mention in a summary beat
   a later category's explicit title — "Workflow Overview" landed in Q&A because
   its summary said "questions". */
function tlCat(title,summary){
  let best=TLCATS[TLCATS.length-1], bestScore=0;
  for(const k of TLCATS.slice(0,-1)){
    let score;
    if(k.kw.test(title||"")) score=3;
    else{
      const g=new RegExp(k.kw.source,"gi");
      score=Math.min(new Set(((summary||"").match(g)||[]).map(m=>m.toLowerCase())).size,2);
    }
    if(score>bestScore){best=k;bestScore=score}
  }
  return bestScore>=1?best:TLCATS[TLCATS.length-1];
}

/* Optional: two more ASR names seen in the live chapters. Append to tlfix's
   existing chain — "QIN models" (Esteban) and "LightLM" (Henry, beside Haiku).

   const tlfix=s=>(s||"").replace(/\bAppify\b/gi,"Apify").replace(/\bCloud Code\b/gi,"Claude Code")
    .replace(/\bQuinn\b/g,"Qwen").replace(/\bQIN\b/g,"Qwen")
    .replace(/\bLight Alarm\b/gi,"LiteLLM").replace(/\bLightLM\b/g,"LiteLLM")
    .replace(/\bLang fuse\b/gi,"Langfuse");
*/
