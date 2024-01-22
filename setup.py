from setuptools import setup, find_packages

setup(
    name='wesnothanalytics',
    version='0.1',
    author='Dark Adept',
    author_email='wesnothanalytics@gmail.com',
    description='A simple replay parser for "Battle for Wesnoth"',
    url='https://github.com/your_username/your_package',
    install_requires=["setuptools"], 
    keywords=["Python","Battle for Wesnoth","Replay Parser"],
    packages=find_packages(),
    include_package_data=True
)