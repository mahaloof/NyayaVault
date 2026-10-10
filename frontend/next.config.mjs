const config={output:process.env.DOCKER_BUILD?"standalone":undefined,poweredByHeader:false,async headers(){return [{source:"/:path*",headers:[{key:"X-Frame-Options",value:"DENY"},{key:"X-Content-Type-Options",value:"nosniff"},{key:"Referrer-Policy",value:"same-origin"}]}]}};
export default config;
