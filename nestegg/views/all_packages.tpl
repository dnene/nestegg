<html>
	<head>
		<title>Simple Index</title>
	</head>
	<body>
	%for name in pkgs:
	    <a href="{{name}}/">{{name}}</a><br/>
	%end
	</body>
</html>