<html>
	<head>
		<title>{{name}}</title>
	</head>
	<body>
		<h1>{{name}}</h1>
		%for file, hash in versions.items():
			<a href="{{file}}#{{hash}}" rel="download">{{file}}</a><br/>
		%end
	</body>
</html>
