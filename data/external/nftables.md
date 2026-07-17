<!DOCTYPE html>
<html class="client-nojs" lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<title>nftables wiki</title>
<script>(function(){var className="client-js";var cookie=document.cookie.match(/(?:^|; )wikidb_nftablesmwclientpreferences=([^;]+)/);if(cookie){cookie[1].split('%2C').forEach(function(pref){className=className.replace(new RegExp('(^| )'+pref.replace(/-clientpref-\w+$|[^\w-]+/g,'')+'-clientpref-\\w+( |$)'),'$1'+pref+'$2');});}document.documentElement.className=className;}());RLCONF={"wgBreakFrames":false,"wgSeparatorTransformTable":["",""],"wgDigitTransformTable":["",""],"wgDefaultDateFormat":"dmy","wgMonthNames":["","January","February","March","April","May","June","July","August","September","October","November","December"],"wgRequestId":"aljZEgR-2nX_zHlLGe4OvwAAAAM","wgCanonicalNamespace":"","wgCanonicalSpecialPageName":false,"wgNamespaceNumber":0,"wgPageName":"Main_Page","wgTitle":"Main Page","wgCurRevisionId":1152,"wgRevisionId":1152,"wgArticleId":1,"wgIsArticle":true,"wgIsRedirect":false,"wgAction":"view","wgUserName":null,"wgUserGroups":["*"],"wgCategories":[],"wgPageViewLanguage":"en","wgPageContentLanguage":"en","wgPageContentModel":"wikitext","wgRelevantPageName":"Main_Page","wgRelevantArticleId":1,"wgIsProbablyEditable":false,"wgRelevantPageIsProbablyEditable":false,"wgRestrictionEdit":[],"wgRestrictionMove":[],"wgIsMainPage":true};
RLSTATE={"site.styles":"ready","user.styles":"ready","user":"ready","user.options":"loading","skins.vector.styles.legacy":"ready"};RLPAGEMODULES=["site","mediawiki.page.ready","mediawiki.toc","skins.vector.legacy.js"];</script>
<script>(RLQ=window.RLQ||[]).push(function(){mw.loader.impl(function(){return["user.options@12s5i",function($,jQuery,require,module){mw.user.tokens.set({"patrolToken":"+\\","watchToken":"+\\","csrfToken":"+\\"});
}];});});</script>
<link rel="stylesheet" href="/wiki-nftables/load.php?lang=en&amp;modules=skins.vector.styles.legacy&amp;only=styles&amp;skin=vector">
<script async="" src="/wiki-nftables/load.php?lang=en&amp;modules=startup&amp;only=scripts&amp;raw=1&amp;skin=vector"></script>
<meta name="generator" content="MediaWiki 1.43.6">
<meta name="robots" content="max-image-preview:standard">
<meta name="format-detection" content="telephone=no">
<meta name="viewport" content="width=1120">
<link rel="search" type="application/opensearchdescription+xml" href="/wiki-nftables/rest.php/v1/search" title="nftables wiki (en)">
<link rel="EditURI" type="application/rsd+xml" href="http://wiki.nftables.org/wiki-nftables/api.php?action=rsd">
<link rel="license" href="https://www.gnu.org/copyleft/fdl.html">
<link rel="alternate" type="application/atom+xml" title="nftables wiki Atom feed" href="/wiki-nftables/index.php?title=Special:RecentChanges&amp;feed=atom">
</head>
<body class="skin-vector-legacy mediawiki ltr sitedir-ltr mw-hide-empty-elt ns-0 ns-subject page-Main_Page rootpage-Main_Page skin-vector action-view"><div id="mw-page-base" class="noprint"></div>
<div id="mw-head-base" class="noprint"></div>
<div id="content" class="mw-body" role="main">
	<a id="top"></a>
	<div id="siteNotice"></div>
	<div class="mw-indicators">
	</div>
	<h1 id="firstHeading" class="firstHeading mw-first-heading"><span class="mw-page-title-main">Main Page</span></h1>
	<div id="bodyContent" class="vector-body">
		<div id="siteSub" class="noprint">From nftables wiki</div>
		<div id="contentSub"><div id="mw-content-subtitle"></div></div>
		<div id="contentSub2"></div>
		
		<div id="jump-to-nav"></div>
		<a class="mw-jump-link" href="#mw-head">Jump to navigation</a>
		<a class="mw-jump-link" href="#searchInput">Jump to search</a>
		<div id="mw-content-text" class="mw-body-content"><div class="mw-content-ltr mw-parser-output" lang="en" dir="ltr"><p>Welcome to the <i>nftables</i> HOWTO documentation page. Here you will find documentation on how to build, install, configure and use nftables.
</p><p>If you have any suggestion to improve it, please send your comments to Netfilter users mailing list &lt;netfilter@vger.kernel.org&gt;.
</p><p><br />
</p>
<div id="toc" class="toc" role="navigation" aria-labelledby="mw-toc-heading"><input type="checkbox" role="button" id="toctogglecheckbox" class="toctogglecheckbox" style="display:none" /><div class="toctitle" lang="en" dir="ltr"><h2 id="mw-toc-heading">Contents</h2><span class="toctogglespan"><label class="toctogglelabel" for="toctogglecheckbox"></label></span></div>
<ul>
<li class="toclevel-1 tocsection-1"><a href="#News"><span class="tocnumber">1</span> <span class="toctext">News</span></a></li>
<li class="toclevel-1 tocsection-2"><a href="#Introduction"><span class="tocnumber">2</span> <span class="toctext">Introduction</span></a></li>
<li class="toclevel-1 tocsection-3"><a href="#Reference"><span class="tocnumber">3</span> <span class="toctext">Reference</span></a></li>
<li class="toclevel-1 tocsection-4"><a href="#Installing_nftables"><span class="tocnumber">4</span> <span class="toctext">Installing nftables</span></a></li>
<li class="toclevel-1 tocsection-5"><a href="#Upgrading_from_xtables_to_nftables"><span class="tocnumber">5</span> <span class="toctext">Upgrading from xtables to nftables</span></a></li>
<li class="toclevel-1 tocsection-6"><a href="#Basic_operation"><span class="tocnumber">6</span> <span class="toctext">Basic operation</span></a></li>
<li class="toclevel-1 tocsection-7"><a href="#Expressions:_Matching_packets"><span class="tocnumber">7</span> <span class="toctext">Expressions: Matching packets</span></a></li>
<li class="toclevel-1 tocsection-8"><a href="#Statements:_Acting_on_packet_matches"><span class="tocnumber">8</span> <span class="toctext">Statements: Acting on packet matches</span></a></li>
<li class="toclevel-1 tocsection-9"><a href="#Advanced_data_structures_for_performance_packet_classification"><span class="tocnumber">9</span> <span class="toctext">Advanced data structures for performance packet classification</span></a></li>
<li class="toclevel-1 tocsection-10"><a href="#Examples"><span class="tocnumber">10</span> <span class="toctext">Examples</span></a></li>
<li class="toclevel-1 tocsection-11"><a href="#Development"><span class="tocnumber">11</span> <span class="toctext">Development</span></a></li>
<li class="toclevel-1 tocsection-12"><a href="#External_links"><span class="tocnumber">12</span> <span class="toctext">External links</span></a></li>
<li class="toclevel-1 tocsection-13"><a href="#Thanks"><span class="tocnumber">13</span> <span class="toctext">Thanks</span></a></li>
</ul>
</div>

<h1><span class="mw-headline" id="News"><a href="/wiki-nftables/index.php/News" title="News">News</a></span></h1>
<h1><span class="mw-headline" id="Introduction">Introduction</span></h1>
<ul><li><a href="/wiki-nftables/index.php/What_is_nftables%3F" title="What is nftables?">What is nftables?</a></li>
<li><a href="/wiki-nftables/index.php/How_to_obtain_help/support" title="How to obtain help/support">How to obtain help/support</a></li></ul>
<p><br />
</p>
<h1><span class="mw-headline" id="Reference">Reference</span></h1>
<ul><li><a rel="nofollow" class="external text" href="https://www.netfilter.org/projects/nftables/manpage.html">man nft - netfilter website</a></li>
<li><a rel="nofollow" class="external text" href="https://www.mankier.com/8/nft">man nft - mankier.com</a></li>
<li><a href="/wiki-nftables/index.php/Quick_reference-nftables_in_10_minutes" title="Quick reference-nftables in 10 minutes">Quick reference, nftables in 10 minutes</a></li>
<li><a href="/wiki-nftables/index.php/Netfilter_hooks" title="Netfilter hooks">Netfilter hooks</a> and nftables integration with existing Netfilter components</li>
<li><a href="/wiki-nftables/index.php/Nftables_families" title="Nftables families">Understanding nftables families</a></li>
<li><a href="/wiki-nftables/index.php/Data_types" title="Data types">Data types</a></li>
<li><a href="/wiki-nftables/index.php/Connection_Tracking_System" title="Connection Tracking System">Connection tracking system (conntrack)</a>, used for stateful firewalling and NAT</li>
<li><a href="/wiki-nftables/index.php/Troubleshooting" title="Troubleshooting">Troubleshooting and FAQ</a></li>
<li><a href="/wiki-nftables/index.php/Further_documentation" title="Further documentation">Additional documentation</a></li></ul>
<p><br />
</p>
<h1><span class="mw-headline" id="Installing_nftables">Installing nftables</span></h1>
<ul><li><a href="/wiki-nftables/index.php/Nftables_from_distributions" title="Nftables from distributions">Using nftables from distributions</a></li>
<li><a href="/wiki-nftables/index.php/Building_and_installing_nftables_from_sources" title="Building and installing nftables from sources">Building and installing nftables from sources</a></li></ul>
<p><br />
</p>
<h1><span class="mw-headline" id="Upgrading_from_xtables_to_nftables">Upgrading from xtables to nftables</span></h1>
<ul><li><a href="/wiki-nftables/index.php/Legacy_xtables_tools" title="Legacy xtables tools">Legacy xtables tools</a></li>
<li><a href="/wiki-nftables/index.php/Moving_from_iptables_to_nftables" title="Moving from iptables to nftables">Moving from iptables to nftables</a></li>
<li><a href="/wiki-nftables/index.php/Moving_from_ipset_to_nftables" title="Moving from ipset to nftables">Moving from ipset to nftables</a></li></ul>
<p><br />
</p>
<h1><span class="mw-headline" id="Basic_operation">Basic operation</span></h1>
<ul><li><a href="/wiki-nftables/index.php/Configuring_tables" title="Configuring tables">Configuring tables</a></li>
<li><a href="/wiki-nftables/index.php/Configuring_chains" title="Configuring chains">Configuring chains</a></li>
<li><a href="/wiki-nftables/index.php/Simple_rule_management" title="Simple rule management">Simple rule management</a></li>
<li><a href="/wiki-nftables/index.php/Atomic_rule_replacement" title="Atomic rule replacement">Atomic rule replacement</a></li>
<li><a href="/wiki-nftables/index.php/Error_reporting_from_the_command_line" title="Error reporting from the command line">Error reporting from the command line</a></li>
<li><a href="/wiki-nftables/index.php/Building_rules_through_expressions" title="Building rules through expressions">Building rules through expressions</a></li>
<li><a href="/wiki-nftables/index.php/Operations_at_ruleset_level" title="Operations at ruleset level">Operations at ruleset level</a></li>
<li><a href="/wiki-nftables/index.php/Monitoring_ruleset_updates" title="Monitoring ruleset updates">Monitoring ruleset updates</a></li>
<li><a href="/wiki-nftables/index.php/Scripting" title="Scripting">Scripting</a></li>
<li><a href="/wiki-nftables/index.php/Ruleset_debug/tracing" title="Ruleset debug/tracing">Ruleset debug/tracing</a></li>
<li><a href="/wiki-nftables/index.php/Ruleset_debug/VM_code_analysis" title="Ruleset debug/VM code analysis">Ruleset debug/VM code analysis</a></li>
<li><a href="/wiki-nftables/index.php/Output_text_modifiers" title="Output text modifiers">Output text modifiers</a></li></ul>
<h1><span class="mw-headline" id="Expressions:_Matching_packets">Expressions: Matching packets</span></h1>
<ul><li><a href="/wiki-nftables/index.php/Matching_packet_metainformation" title="Matching packet metainformation">Matching packet metainformation</a></li>
<li><a href="/wiki-nftables/index.php/Matching_packet_headers" title="Matching packet headers">Matching packet headers</a></li>
<li><a href="/wiki-nftables/index.php/Matching_connection_tracking_stateful_metainformation" title="Matching connection tracking stateful metainformation">Matching connection tracking stateful metainformation</a></li>
<li><a href="/wiki-nftables/index.php/Matching_routing_information" title="Matching routing information">Matching routing information</a></li>
<li><a href="/wiki-nftables/index.php/Rate_limiting_matchings" title="Rate limiting matchings">Rate limiting matchings</a></li></ul>
<p><br />
</p>
<h1><span class="mw-headline" id="Statements:_Acting_on_packet_matches">Statements: Acting on packet matches</span></h1>
<ul><li><a href="/wiki-nftables/index.php/Accepting_and_dropping_packets" title="Accepting and dropping packets">Accepting and dropping packets</a></li>
<li><a href="/wiki-nftables/index.php/Rejecting_traffic" title="Rejecting traffic">Rejecting traffic</a></li>
<li><a href="/wiki-nftables/index.php/Jumping_to_chain" title="Jumping to chain">Jumping to chain</a></li>
<li><a href="/wiki-nftables/index.php/Counters" title="Counters">Counters</a></li>
<li><a href="/wiki-nftables/index.php/Logging_traffic" title="Logging traffic">Logging traffic</a></li>
<li><a href="/wiki-nftables/index.php/Performing_Network_Address_Translation_(NAT)" title="Performing Network Address Translation (NAT)">Performing Network Address Translation (NAT)</a></li>
<li><a href="/wiki-nftables/index.php/Setting_packet_metainformation" title="Setting packet metainformation">Setting packet metainformation</a></li>
<li><a href="/wiki-nftables/index.php/Setting_packet_connection_tracking_metainformation" title="Setting packet connection tracking metainformation">Setting packet connection tracking metainformation</a></li>
<li><a href="/wiki-nftables/index.php/Mangling_packet_headers" title="Mangling packet headers">Mangling packet headers</a> (including stateless NAT)</li>
<li><a href="/wiki-nftables/index.php/Duplicating_packets" title="Duplicating packets">Duplicating packets</a></li>
<li><a href="/wiki-nftables/index.php/Load_balancing" title="Load balancing">Load balancing</a></li>
<li><a href="/wiki-nftables/index.php/Queueing_to_userspace" title="Queueing to userspace">Queueing to userspace</a></li></ul>
<p><br />
</p>
<h1><span class="mw-headline" id="Advanced_data_structures_for_performance_packet_classification">Advanced data structures for performance packet classification</span></h1>
<ul><li><a href="/wiki-nftables/index.php/Intervals" title="Intervals">Intervals</a></li>
<li><a href="/wiki-nftables/index.php/Concatenations" title="Concatenations">Concatenations</a></li>
<li><a href="/wiki-nftables/index.php/Math_operations" title="Math operations">Math operations</a></li>
<li><a href="/wiki-nftables/index.php/Stateful_objects" title="Stateful objects">Stateful objects</a>
<ul><li><a href="/wiki-nftables/index.php/Counters" title="Counters">Counters</a></li>
<li><a href="/wiki-nftables/index.php/Quotas" title="Quotas">Quotas</a></li>
<li><a href="/wiki-nftables/index.php/Limits" title="Limits">Limits</a></li>
<li><a href="/wiki-nftables/index.php/Connlimits" title="Connlimits">Connlimits</a> (<i>ct count</i>)</li></ul></li>
<li>Other objects
<ul><li><a href="/wiki-nftables/index.php/Conntrack_helpers" title="Conntrack helpers">Conntrack helpers</a> (<i>ct helper</i>, Layer 7 ALG)</li>
<li><a href="/wiki-nftables/index.php/Ct_timeout" title="Ct timeout">Conntrack timeout policies</a> (<i>ct timeout</i>)</li>
<li><a href="/wiki-nftables/index.php/Ct_expectation" title="Ct expectation">Conntrack expectations</a> (<i>ct expectation</i>)</li>
<li><a href="/wiki-nftables/index.php/Synproxy" title="Synproxy">Synproxy</a></li>
<li><a href="/wiki-nftables/index.php/Secmark" title="Secmark">Secmarks</a></li></ul></li>
<li>Generic set infrastructure
<ul><li><a href="/wiki-nftables/index.php/Sets" title="Sets">Sets</a></li>
<li><a href="/wiki-nftables/index.php/Element_timeouts" title="Element timeouts">Element timeouts</a></li>
<li><a href="/wiki-nftables/index.php/Updating_sets_from_the_packet_path" title="Updating sets from the packet path">Updating sets from the packet path</a></li>
<li><a href="/wiki-nftables/index.php/Maps" title="Maps">Maps</a></li>
<li><a href="/wiki-nftables/index.php/Verdict_Maps_(vmaps)" title="Verdict Maps (vmaps)"> Verdict maps</a></li>
<li><a href="/wiki-nftables/index.php/Meters" title="Meters">Metering</a> (formerly known as flow tables before nftables 0.8.1)</li></ul></li>
<li><a href="/wiki-nftables/index.php/Flowtables" title="Flowtables">Flowtables</a> (the fastpath network stack bypass)</li></ul>
<p><br />
</p>
<h1><span class="mw-headline" id="Examples">Examples</span></h1>
<ul><li><a href="/wiki-nftables/index.php/Simple_ruleset_for_a_workstation" title="Simple ruleset for a workstation">Simple ruleset for a workstation</a></li>
<li><a href="/wiki-nftables/index.php/Simple_ruleset_for_a_server" title="Simple ruleset for a server">Simple ruleset for a server</a></li>
<li><a href="/wiki-nftables/index.php/Simple_ruleset_for_a_home_router" title="Simple ruleset for a home router">Simple ruleset for a home router</a></li>
<li><a href="/wiki-nftables/index.php/Bridge_filtering" title="Bridge filtering">Bridge filtering</a></li>
<li><a href="/wiki-nftables/index.php/Multiple_NATs_using_nftables_maps" title="Multiple NATs using nftables maps">Multiple NATs using nftables maps</a></li>
<li><a href="/wiki-nftables/index.php/Classic_perimetral_firewall_example" title="Classic perimetral firewall example">Classic perimetral firewall example</a></li>
<li><a href="/wiki-nftables/index.php/Port_knocking_example" title="Port knocking example">Port knocking example</a></li>
<li><a href="/wiki-nftables/index.php/Classification_to_tc_structure_example" title="Classification to tc structure example">Classification to tc structure example</a></li>
<li><a href="/wiki-nftables/index.php/Using_configuration_management_systems" title="Using configuration management systems">Using configuration management systems</a> (like puppet, ansible, etc)</li>
<li><a href="/wiki-nftables/index.php/GeoIP_matching" title="GeoIP matching">GeoIP matching</a></li></ul>
<h1><span class="mw-headline" id="Development">Development</span></h1>
<p>Check <a href="/wiki-nftables/index.php/Portal:DeveloperDocs" title="Portal:DeveloperDocs">Portal:DeveloperDocs - documentation for netfilter developers</a>.
</p><p>Some hints on the general development progress:
</p>
<ul><li><a href="/wiki-nftables/index.php/List_of_updates_since_Linux_kernel_3.13" title="List of updates since Linux kernel 3.13">List of updates since Linux kernel 3.13</a></li>
<li><a href="/wiki-nftables/index.php/List_of_updates_in_the_nft_command_line_tool" title="List of updates in the nft command line tool">List of updates in the nft command line tool</a></li>
<li><a href="/wiki-nftables/index.php/Supported_features_compared_to_xtables" title="Supported features compared to xtables">Supported features compared to {ip,ip6,eb,arp}tables</a></li>
<li><a href="/wiki-nftables/index.php/List_of_available_translations_via_iptables-translate_tool" title="List of available translations via iptables-translate tool">List of available translations via iptables-translate tool</a></li></ul>
<p><br />
</p>
<h1><span class="mw-headline" id="External_links">External links</span></h1>
<p>Watch some videos:
</p>
<ul><li>Watch <a rel="nofollow" class="external text" href="https://www.youtube.com/watch?v=FXTRRwXi3b4">Getting a grasp of nftables</a>, thanks to <a rel="nofollow" class="external text" href="https://www.nluug.nl/index-en.html">NLUUG association</a> for recording this.</li>
<li>Watch <a rel="nofollow" class="external text" href="https://www.youtube.com/watch?v=CaYp0d2wiuU#t=1m47s">The ultimate packet classifier for GNU/Linux</a>, thanks to the FSFE for paying my trip to Barcelona and for recommending me as speaker to the KDE Spanish branch.</li>
<li><a rel="nofollow" class="external text" href="https://www.youtube.com/watch?v=Sy0JDX451ns">Florian Westphal - Why nftables?</a></li>
<li>Watch <a rel="nofollow" class="external text" href="https://www.youtube.com/watch?v=0wQfSfDVN94">NLUUG - Goodbye iptables, Hello nftables</a></li></ul>
<p>Watch videos to track updates:
</p>
<ul><li>Watch <a rel="nofollow" class="external text" href="https://www.youtube.com/watch?v=qXVOA2MKA1s">Netdev 2.1 - Netfilter mini-workshop (2017)</a></li>
<li>Watch <a rel="nofollow" class="external text" href="https://youtu.be/iCj10vEKPrw">Netdev 2.2 - Netf‌ilter mini-workshop (2018)</a></li>
<li>Watch <a rel="nofollow" class="external text" href="https://youtu.be/0hqfzp6tpZo">Netdev 0x12 - Netf‌ilter mini-workshop (2019)</a></li>
<li>Watch <a rel="nofollow" class="external text" href="https://www.youtube.com/watch?v=GqGGo4svj7s&amp;feature=youtu.be">Netdev 0x14 - Netfilter mini-Workshop (2020)</a></li></ul>
<p>Additional documentations and articles:
</p>
<ul><li>Tutorial <a rel="nofollow" class="external text" href="https://zasdfgbnm.github.io/2017/09/07/Extending-nftables/">Extending nftables by Xiang Gao</a></li>
<li>Article <a rel="nofollow" class="external text" href="http://ral-arturo.org/2017/05/05/debian-stretch-stable-nftables.html">New in Debian stable Stretch: nftables</a></li>
<li>Article <a rel="nofollow" class="external text" href="https://ral-arturo.org/2020/11/22/python-nftables-tutorial.html">How to use nftables from python</a> and git repository <a rel="nofollow" class="external text" href="https://github.com/aborrero/python-nftables-tutorial">python-nftables-tutorial.git</a></li></ul>
<p><br />
</p>
<h1><span class="mw-headline" id="Thanks">Thanks</span></h1>
<p>To the NLnet foundation for initial sponsorship of this HOWTO:
</p><p><a rel="nofollow" class="external text" href="https://nlnet.nl"><img src="https://nlnet.nl/image/logo.gif" alt="logo.gif" /></a>
</p><p>To Eric Leblond, for boostrapping the <a rel="nofollow" class="external text" href="https://home.regit.org/netfilter-en/nftables-quick-howto/">Nftables quick howto</a> in 2013.
</p>
<!-- 
NewPP limit report
Cached time: 20260715175741
Cache expiry: 86400
Reduced expiry: false
Complications: [show‐toc]
CPU time usage: 0.026 seconds
Real time usage: 0.027 seconds
Preprocessor visited node count: 117/1000000
Post‐expand include size: 0/2097152 bytes
Template argument size: 0/2097152 bytes
Highest expansion depth: 2/100
Expensive parser function count: 0/100
Unstrip recursion depth: 0/20
Unstrip post‐expand size: 0/5000000 bytes
-->
<!--
Transclusion expansion time report (%,ms,calls,template)
100.00%    0.000      1 -total
-->

<!-- Saved in parser cache with key wikidb_nftables:pcache:idhash:1-0!canonical and timestamp 20260715175741 and revision id 1152. Rendering was triggered because: page-view
 -->
</div>
<div class="printfooter" data-nosnippet="">Retrieved from "<a dir="ltr" href="http://wiki.nftables.org/wiki-nftables/index.php?title=Main_Page&amp;oldid=1152">http://wiki.nftables.org/wiki-nftables/index.php?title=Main_Page&amp;oldid=1152</a>"</div></div>
		<div id="catlinks" class="catlinks catlinks-allhidden" data-mw="interface"></div>
	</div>
</div>

<div id="mw-navigation">
	<h2>Navigation menu</h2>
	<div id="mw-head">
		
<nav id="p-personal" class="mw-portlet mw-portlet-personal vector-user-menu-legacy vector-menu" aria-labelledby="p-personal-label"  >
	<h3
		id="p-personal-label"
		
		class="vector-menu-heading "
	>
		<span class="vector-menu-heading-label">Personal tools</span>
	</h3>
	<div class="vector-menu-content">
		
		<ul class="vector-menu-content-list">
			
			<li id="pt-login" class="mw-list-item"><a href="/wiki-nftables/index.php?title=Special:UserLogin&amp;returnto=Main+Page" title="You are encouraged to log in; however, it is not mandatory [o]" accesskey="o"><span>Log in</span></a></li>
		</ul>
		
	</div>
</nav>

		<div id="left-navigation">
			
<nav id="p-namespaces" class="mw-portlet mw-portlet-namespaces vector-menu-tabs vector-menu-tabs-legacy vector-menu" aria-labelledby="p-namespaces-label"  >
	<h3
		id="p-namespaces-label"
		
		class="vector-menu-heading "
	>
		<span class="vector-menu-heading-label">Namespaces</span>
	</h3>
	<div class="vector-menu-content">
		
		<ul class="vector-menu-content-list">
			
			<li id="ca-nstab-main" class="selected mw-list-item"><a href="/wiki-nftables/index.php/Main_Page" title="View the content page [c]" accesskey="c"><span>Main Page</span></a></li><li id="ca-talk" class="new mw-list-item"><a href="/wiki-nftables/index.php?title=Talk:Main_Page&amp;action=edit&amp;redlink=1" rel="discussion" class="new" title="Discussion about the content page (page does not exist) [t]" accesskey="t"><span>Discussion</span></a></li>
		</ul>
		
	</div>
</nav>

			
<nav id="p-variants" class="mw-portlet mw-portlet-variants emptyPortlet vector-menu-dropdown vector-menu" aria-labelledby="p-variants-label"  >
	<input type="checkbox"
		id="p-variants-checkbox"
		role="button"
		aria-haspopup="true"
		data-event-name="ui.dropdown-p-variants"
		class="vector-menu-checkbox"
		aria-labelledby="p-variants-label"
	>
	<label
		id="p-variants-label"
		
		class="vector-menu-heading "
	>
		<span class="vector-menu-heading-label">English</span>
	</label>
	<div class="vector-menu-content">
		
		<ul class="vector-menu-content-list">
			
			
		</ul>
		
	</div>
</nav>

		</div>
		<div id="right-navigation">
			
<nav id="p-views" class="mw-portlet mw-portlet-views vector-menu-tabs vector-menu-tabs-legacy vector-menu" aria-labelledby="p-views-label"  >
	<h3
		id="p-views-label"
		
		class="vector-menu-heading "
	>
		<span class="vector-menu-heading-label">Views</span>
	</h3>
	<div class="vector-menu-content">
		
		<ul class="vector-menu-content-list">
			
			<li id="ca-view" class="selected mw-list-item"><a href="/wiki-nftables/index.php/Main_Page"><span>Read</span></a></li><li id="ca-viewsource" class="mw-list-item"><a href="/wiki-nftables/index.php?title=Main_Page&amp;action=edit" title="This page is protected.&#10;You can view its source [e]" accesskey="e"><span>View source</span></a></li><li id="ca-history" class="mw-list-item"><a href="/wiki-nftables/index.php?title=Main_Page&amp;action=history" title="Past revisions of this page [h]" accesskey="h"><span>View history</span></a></li>
		</ul>
		
	</div>
</nav>

			
<nav id="p-cactions" class="mw-portlet mw-portlet-cactions emptyPortlet vector-menu-dropdown vector-menu" aria-labelledby="p-cactions-label"  title="More options" >
	<input type="checkbox"
		id="p-cactions-checkbox"
		role="button"
		aria-haspopup="true"
		data-event-name="ui.dropdown-p-cactions"
		class="vector-menu-checkbox"
		aria-labelledby="p-cactions-label"
	>
	<label
		id="p-cactions-label"
		
		class="vector-menu-heading "
	>
		<span class="vector-menu-heading-label">More</span>
	</label>
	<div class="vector-menu-content">
		
		<ul class="vector-menu-content-list">
			
			
		</ul>
		
	</div>
</nav>

			
<div id="p-search" role="search" class="vector-search-box-vue  vector-search-box-show-thumbnail vector-search-box-auto-expand-width vector-search-box">
	<h3 >Search</h3>
	<form action="/wiki-nftables/index.php" id="searchform" class="vector-search-box-form">
		<div id="simpleSearch"
			class="vector-search-box-inner"
			 data-search-loc="header-navigation">
			<input class="vector-search-box-input"
				 type="search" name="search" placeholder="Search nftables wiki" aria-label="Search nftables wiki" autocapitalize="sentences" title="Search nftables wiki [f]" accesskey="f" id="searchInput"
			>
			<input type="hidden" name="title" value="Special:Search">
			<input id="mw-searchButton"
				 class="searchButton mw-fallbackSearchButton" type="submit" name="fulltext" title="Search the pages for this text" value="Search">
			<input id="searchButton"
				 class="searchButton" type="submit" name="go" title="Go to a page with this exact name if it exists" value="Go">
		</div>
	</form>
</div>

		</div>
	</div>
	
<div id="mw-panel" class="vector-legacy-sidebar">
	<div id="p-logo" role="banner">
		<a class="mw-wiki-logo" href="/wiki-nftables/index.php/Main_Page"
			title="Visit the main page"></a>
	</div>
	
<nav id="p-navigation" class="mw-portlet mw-portlet-navigation vector-menu-portal portal vector-menu" aria-labelledby="p-navigation-label"  >
	<h3
		id="p-navigation-label"
		
		class="vector-menu-heading "
	>
		<span class="vector-menu-heading-label">Navigation</span>
	</h3>
	<div class="vector-menu-content">
		
		<ul class="vector-menu-content-list">
			
			<li id="n-mainpage-description" class="mw-list-item"><a href="/wiki-nftables/index.php/Main_Page" title="Visit the main page [z]" accesskey="z"><span>Main page</span></a></li><li id="n-recentchanges" class="mw-list-item"><a href="/wiki-nftables/index.php/Special:RecentChanges" title="A list of recent changes in the wiki [r]" accesskey="r"><span>Recent changes</span></a></li><li id="n-randompage" class="mw-list-item"><a href="/wiki-nftables/index.php/Special:Random" title="Load a random page [x]" accesskey="x"><span>Random page</span></a></li><li id="n-help-mediawiki" class="mw-list-item"><a href="https://www.mediawiki.org/wiki/Special:MyLanguage/Help:Contents"><span>Help about MediaWiki</span></a></li>
		</ul>
		
	</div>
</nav>

	
<nav id="p-tb" class="mw-portlet mw-portlet-tb vector-menu-portal portal vector-menu" aria-labelledby="p-tb-label"  >
	<h3
		id="p-tb-label"
		
		class="vector-menu-heading "
	>
		<span class="vector-menu-heading-label">Tools</span>
	</h3>
	<div class="vector-menu-content">
		
		<ul class="vector-menu-content-list">
			
			<li id="t-whatlinkshere" class="mw-list-item"><a href="/wiki-nftables/index.php/Special:WhatLinksHere/Main_Page" title="A list of all wiki pages that link here [j]" accesskey="j"><span>What links here</span></a></li><li id="t-recentchangeslinked" class="mw-list-item"><a href="/wiki-nftables/index.php/Special:RecentChangesLinked/Main_Page" rel="nofollow" title="Recent changes in pages linked from this page [k]" accesskey="k"><span>Related changes</span></a></li><li id="t-specialpages" class="mw-list-item"><a href="/wiki-nftables/index.php/Special:SpecialPages" title="A list of all special pages [q]" accesskey="q"><span>Special pages</span></a></li><li id="t-print" class="mw-list-item"><a href="javascript:print();" rel="alternate" title="Printable version of this page [p]" accesskey="p"><span>Printable version</span></a></li><li id="t-permalink" class="mw-list-item"><a href="/wiki-nftables/index.php?title=Main_Page&amp;oldid=1152" title="Permanent link to this revision of this page"><span>Permanent link</span></a></li><li id="t-info" class="mw-list-item"><a href="/wiki-nftables/index.php?title=Main_Page&amp;action=info" title="More information about this page"><span>Page information</span></a></li>
		</ul>
		
	</div>
</nav>

	
</div>

</div>

<footer id="footer" class="mw-footer" >
	<ul id="footer-info">
	<li id="footer-info-lastmod"> This page was last edited on 12 October 2024, at 13:47.</li>
	<li id="footer-info-copyright">Content is available under <a class="external" rel="nofollow" href="https://www.gnu.org/copyleft/fdl.html">GNU Free Documentation License 1.3 or later</a> unless otherwise noted.</li>
</ul>

	<ul id="footer-places">
	<li id="footer-places-privacy"><a href="/wiki-nftables/index.php/Nftables:Privacy_policy">Privacy policy</a></li>
	<li id="footer-places-about"><a href="/wiki-nftables/index.php/Nftables:About">About nftables wiki</a></li>
	<li id="footer-places-disclaimers"><a href="/wiki-nftables/index.php/Nftables:General_disclaimer">Disclaimers</a></li>
</ul>

	<ul id="footer-icons" class="noprint">
	<li id="footer-copyrightico"><a href="https://www.gnu.org/copyleft/fdl.html" class="cdx-button cdx-button--fake-button cdx-button--size-large cdx-button--fake-button--enabled"><img src="/wiki-nftables/resources/assets/licenses/gnu-fdl.png" alt="GNU Free Documentation License 1.3 or later" width="88" height="31" loading="lazy"></a></li>
	<li id="footer-poweredbyico"><a href="https://www.mediawiki.org/" class="cdx-button cdx-button--fake-button cdx-button--size-large cdx-button--fake-button--enabled"><img src="/wiki-nftables/resources/assets/poweredby_mediawiki.svg" alt="Powered by MediaWiki" width="88" height="31" loading="lazy"></a></li>
</ul>

</footer>

<script>(RLQ=window.RLQ||[]).push(function(){mw.config.set({"wgBackendResponseTime":127,"wgPageParseReport":{"limitreport":{"cputime":"0.026","walltime":"0.027","ppvisitednodes":{"value":117,"limit":1000000},"postexpandincludesize":{"value":0,"limit":2097152},"templateargumentsize":{"value":0,"limit":2097152},"expansiondepth":{"value":2,"limit":100},"expensivefunctioncount":{"value":0,"limit":100},"unstrip-depth":{"value":0,"limit":20},"unstrip-size":{"value":0,"limit":5000000},"timingprofile":["100.00%    0.000      1 -total"]},"cachereport":{"timestamp":"20260715175741","ttl":86400,"transientcontent":false}}});});</script>
</body>
</html>