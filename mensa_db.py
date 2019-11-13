#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
engine = create_engine('sqlite:///mensausers.sqlite')
Session = sessionmaker(bind=engine)


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    notifications = Column(Integer(), nullable=False)
    current_selection = Column(String(255), nullable=True)
    user_group = Column(String(255), nullable=True)
    counter = Column(Integer(), nullable=True)
    message_id = Column(Integer(), nullable=True)
    dailymsg = Column(String(5), nullable=True)
    daily_selection = Column(Integer(), nullable=True)


Base.metadata.create_all(engine)
